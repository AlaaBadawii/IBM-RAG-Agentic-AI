import logging
import re
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langgraph.graph import END, StateGraph

from .research_agent import ResearchAgent
from .verification_agent import VerificationAgent
from .relevance_checker import RelevanceChecker


logger = logging.getLogger(__name__)

RelevanceDecision = Literal["CAN_ANSWER", "PARTIAL", "NO_MATCH"]
WorkflowStatus = Literal["in_progress", "irrelevant", "verified", "unverified"]

MAX_RESEARCH_ATTEMPTS = 3

IRRELEVANT_MESSAGE = (
    "I couldn't find enough relevant information in the uploaded "
    "documents to answer this question. Please ask a question related "
    "to the available documents."
)

UNVERIFIED_MESSAGE = (
    "I couldn't produce an answer that passed verification after "
    "multiple research attempts. Please rephrase the question or "
    "provide additional relevant documents."
)

# ``Supported: YES`` / ``Relevant: NO`` on their own lines, case-insensitive.
# Anything else is left to the caller to treat as unresolved.
_VERIFICATION_LINE_PATTERN = re.compile(
    r"^\s*(supported|relevant)\s*:\s*(yes|no)\s*[.!]?\s*$",
    re.IGNORECASE,
)


class AgentState(TypedDict):
    """Data passed between nodes in the LangGraph workflow."""

    question: str
    documents: list[Document]
    draft_answer: str
    verification_report: str
    is_relevant: bool
    research_attempts: int
    status: WorkflowStatus


class AgentWorkflow:
    """Coordinate relevance checking, research, and answer verification.

    Retry policy: at most ``max_research_attempts`` research calls per
    question, with the initial call counting as attempt 1. If verification
    fails on the final attempt, the workflow returns ``UNVERIFIED_MESSAGE``
    with status ``"unverified"`` and preserves the last verification report.
    An unverified draft is never reported as verified.

    Re-research limitation: ``ResearchAgent.research(question, documents)``
    has no feedback parameter, so retries re-run the same question against
    the same document set. Bounded retries guarantee termination, but they
    are not claimed to incorporate verifier feedback.

    Retrieval ownership: ``full_pipeline`` retrieves documents exactly once.
    The relevance checker, research agent, and verifier all receive that same
    document set.
    """

    def __init__(self, max_research_attempts: int = MAX_RESEARCH_ATTEMPTS) -> None:
        if (
            isinstance(max_research_attempts, bool)
            or not isinstance(max_research_attempts, int)
            or max_research_attempts < 1
        ):
            raise ValueError("max_research_attempts must be a positive integer.")

        self.max_research_attempts = max_research_attempts
        self.researcher = ResearchAgent()
        self.verifier = VerificationAgent()
        self.relevance_checker = RelevanceChecker()

        # Build and compile the graph once per workflow instance.
        self.compiled_workflow = self.build_workflow()

    def build_workflow(self):
        """Create and compile the agent workflow."""

        workflow = StateGraph(AgentState)

        workflow.add_node(
            "check_relevance",
            self._check_relevance_step,
        )
        workflow.add_node(
            "research",
            self._research_step,
        )
        workflow.add_node(
            "verify",
            self._verification_step,
        )
        workflow.add_node(
            "finalize_unverified",
            self._finalize_unverified_step,
        )

        workflow.set_entry_point("check_relevance")

        workflow.add_conditional_edges(
            "check_relevance",
            self._decide_after_relevance_check,
            {
                "relevant": "research",
                "irrelevant": END,
            },
        )

        workflow.add_edge("research", "verify")

        workflow.add_conditional_edges(
            "verify",
            self._decide_next_step,
            {
                "retry": "research",
                "end": END,
                "unverified": "finalize_unverified",
            },
        )

        workflow.add_edge("finalize_unverified", END)

        return workflow.compile()

    def full_pipeline(
        self,
        question: str,
        retriever: BaseRetriever,
    ) -> dict[str, str]:
        """Run the complete workflow for a user question."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must be a non-empty string.")

        question = question.strip()

        logger.info("Starting agent workflow.")

        try:
            # Retrieve once. Both relevance checking and research use
            # this same document set.
            documents = retriever.invoke(question)

            logger.info(
                "Retrieved %d documents for the workflow.",
                len(documents),
            )

            initial_state: AgentState = {
                "question": question,
                "documents": documents,
                "draft_answer": "",
                "verification_report": "",
                "is_relevant": False,
                "research_attempts": 0,
                "status": "in_progress",
            }

            # Derive the recursion limit from the retry policy so a large
            # configured attempt count cannot hit LangGraph's default limit
            # (each attempt runs a research node and a verify node).
            final_state = self.compiled_workflow.invoke(
                initial_state,
                config={"recursion_limit": 2 * self.max_research_attempts + 5},
            )

        except Exception:
            logger.exception("Agent workflow execution failed.")
            raise

        result = {
            "draft_answer": final_state.get("draft_answer", ""),
            "verification_report": final_state.get(
                "verification_report",
                "",
            ),
            "status": final_state.get("status", "failed"),
        }

        logger.info(
            "Agent workflow finished with status %s after %d research attempt(s).",
            result["status"],
            final_state.get("research_attempts", 0),
        )

        return result

    def _check_relevance_step(
        self,
        state: AgentState,
    ) -> dict:
        """Determine whether the retrieved documents can answer the question."""

        if not state["documents"]:
            classification = "NO_MATCH"
        else:
            # Reuse the documents retrieved for this batch instead of
            # letting the checker retrieve a second, possibly different set.
            classification = self.relevance_checker.check(
                question=state["question"],
                documents=state["documents"],
            )

        valid_classifications: set[RelevanceDecision] = {
            "CAN_ANSWER",
            "PARTIAL",
            "NO_MATCH",
        }

        if classification not in valid_classifications:
            raise ValueError(
                "RelevanceChecker returned an unexpected classification: "
                f"{classification!r}."
            )

        if classification == "NO_MATCH":
            logger.info("Question rejected by relevance checking.")

            return {
                "is_relevant": False,
                "draft_answer": IRRELEVANT_MESSAGE,
                "verification_report": (
                    "Verification not performed: no relevant documents found."
                ),
                "status": "irrelevant",
            }

        logger.info(
            "Relevance check passed with classification %s.",
            classification,
        )

        return {
            "is_relevant": True,
            "status": "in_progress",
        }

    def _decide_after_relevance_check(
        self,
        state: AgentState,
    ) -> Literal["relevant", "irrelevant"]:
        """Route relevant questions to research."""

        if state["is_relevant"]:
            return "relevant"

        return "irrelevant"

    def _research_step(self, state: AgentState) -> dict:
        """Generate a draft answer from the available documents.

        Retries call the agent with the same question and document set
        because ``ResearchAgent.research`` exposes no feedback parameter.
        """

        attempt = state["research_attempts"] + 1

        logger.info(
            "Starting research attempt %d of %d.",
            attempt,
            self.max_research_attempts,
        )

        research = getattr(self.researcher, "research", None)
        if not callable(research):
            raise AttributeError(
                "ResearchAgent must provide a callable research method."
            )

        result = research(
            state["question"],
            state["documents"],
        )

        if not isinstance(result, dict):
            raise TypeError("ResearchAgent must return a dictionary.")

        draft_answer = result.get("draft_answer")

        if not isinstance(draft_answer, str) or not draft_answer.strip():
            raise ValueError("ResearchAgent returned an empty or invalid draft answer.")

        return {
            "draft_answer": draft_answer,
            "research_attempts": attempt,
        }

    def _verification_step(self, state: AgentState) -> dict:
        """Verify the draft answer against the retrieved documents.

        The verifier returns a textual report with one ``Supported:`` line and
        one ``Relevant:`` line. Malformed or ambiguous reports are recorded as
        unresolved and never count as verification success.
        """

        logger.info(
            "Verifying research attempt %d.",
            state["research_attempts"],
        )

        verify = getattr(self.verifier, "verify", None)
        if not callable(verify):
            raise AttributeError(
                "VerificationAgent must provide a callable verify method."
            )

        result = verify(
            state["draft_answer"],
            state["documents"],
        )

        if not isinstance(result, dict):
            raise TypeError("VerificationAgent must return a dictionary.")

        report = result.get("verification_report")

        if not isinstance(report, str) or not report.strip():
            raise ValueError("VerificationAgent returned an empty or invalid report.")

        verified, outcome = self._parse_verification_report(report)

        logger.info("Verification outcome: %s.", outcome)

        update: dict = {"verification_report": report}

        if verified:
            update["status"] = "verified"

        return update

    @staticmethod
    def _parse_verification_report(report: str) -> tuple[bool, str]:
        """Parse the documented ``Supported``/``Relevant`` report lines.

        Returns ``(verified, outcome)`` where ``outcome`` is one of
        ``verified``, ``unsupported``, ``irrelevant``,
        ``unsupported_irrelevant``, or ``malformed``. Missing, conflicting,
        or unrecognized decisions are unresolved, never verified.
        """

        decisions: dict[str, bool] = {}

        for line in report.splitlines():
            match = _VERIFICATION_LINE_PATTERN.match(line)

            if match is None:
                continue

            field = match.group(1).lower()
            value = match.group(2).lower() == "yes"

            if field in decisions and decisions[field] != value:
                return False, "malformed"

            decisions[field] = value

        if set(decisions) != {"supported", "relevant"}:
            return False, "malformed"

        supported = decisions["supported"]
        relevant = decisions["relevant"]

        if supported and relevant:
            return True, "verified"

        if not supported and not relevant:
            return False, "unsupported_irrelevant"

        if not supported:
            return False, "unsupported"

        return False, "irrelevant"

    def _decide_next_step(
        self,
        state: AgentState,
    ) -> Literal["retry", "end", "unverified"]:
        """Accept verified answers or retry within the configured limit."""

        report = state["verification_report"]
        verified, _ = self._parse_verification_report(report)

        if verified:
            logger.info("Verification accepted the draft answer.")
            return "end"

        if state["research_attempts"] < self.max_research_attempts:
            logger.warning(
                "Verification rejected attempt %d of %d; retrying research.",
                state["research_attempts"],
                self.max_research_attempts,
            )
            return "retry"

        logger.warning(
            "Verification still failing after %d research attempt(s).",
            state["research_attempts"],
        )
        return "unverified"

    @staticmethod
    def _finalize_unverified_step(state: AgentState) -> dict:
        """Return an explicit failure result when retries are exhausted."""

        logger.warning(
            "Terminating unverified after %d research attempt(s).",
            state["research_attempts"],
        )

        return {
            "draft_answer": UNVERIFIED_MESSAGE,
            "status": "unverified",
        }
