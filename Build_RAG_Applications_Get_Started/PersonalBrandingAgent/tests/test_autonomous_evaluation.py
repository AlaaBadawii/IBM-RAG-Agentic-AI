"""Step 13: end-to-end autonomous evaluation.

Workflow-level scenarios that exercise the real application layers together —
``run_sync`` / ``run_branding`` over the real sync pipeline, the real
``BrandingAgent`` (real generator, real verifier), the real publishing
service, and the real notification service — with external side effects
replaced by deterministic fakes:

* isolated temporary SQLite state (never the production database),
* isolated temporary Chroma collections with deterministic fake embeddings,
* a fake LLM client, a fake advisory judge, a fake reasoner,
* a fake LinkedIn transport (or a fake HTTP layer under the real
  ``publish_to_linkedin``, so the real Step 5 classification runs),
* a fake email transport (including a deterministically failing one),
* throwaway git repositories under ``tmp_path`` (never the real workspace).

Every scenario asserts its **recorded** outcome and persistent state — never
just completion, never log strings. A socket-blocking autouse fixture proves
no test can reach the network even by accident.
"""
import base64
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import requests

from app.agent import (
    BrandingAgent,
    ReasoningAnswer,
)
from app.context.builder import build_context
from app.generation import PostGenerator
from app.integrations.linkedin.client import LinkedInClient
from app.integrations.linkedin.enums import PublicationOutcome
from app.integrations.linkedin.models import PublicationResult
from app.integrations.linkedin.publisher import publish_to_linkedin
from app.notify import NotificationService
from app.notify.enums import NotificationFailureCategory
from app.notify.errors import NotificationDeliveryError
from app.publishing import (
    PublishingHistory,
    PublishingService,
    PublishRequest,
    evidence_ref,
)
from app.retrieval.models import RetrievalResult, RetrievedDocument
from app.sources.models import Registry
from app.state import RunOutcome, StateStore
from app.state.enums import DeliveryState, LifecycleState, PublishState, Workflow
from app.state.models import to_iso, utc_now
from app.verification import EvidenceVerifier, JudgeVerdict
from app.workflows import (
    EXIT_LOCKED,
    BrandingConfig,
    SyncConfig,
    run_branding,
    run_sync,
)
from app.workflows.scheduled import WorkflowLocked, lock_name_for
from tests.conftest import PROJECT_ROOT, FakeEmbeddings


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

EVIDENCE_TEXT = (
    "Built a shipment API with FastAPI and SQLAlchemy models and Alembic "
    "migrations; the API returns shipments to the tracking dashboard."
)
#: Passes Step 9 against EVIDENCE_TEXT (same proven pair as the Agent suite).
PASSING_POST = "I built a shipment API with FastAPI and SQLAlchemy models."
WEAK_POST = "I mastered distributed systems across 3 production clusters."
COURSE_TEXT = "Learning distributed systems."
STYLE_TEXT = "Write directly, without marketing language."


# ------------------------------------------------------------------ network ---

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No scenario may open a socket. Fakes stand in for every boundary."""
    def _blocked(*args, **kwargs):
        raise RuntimeError("network access is forbidden in evaluation tests")

    monkeypatch.setattr(socket, "socket", _blocked)


# -------------------------------------------------------------------- fakes ---

def doc(source, *, category, chunk_id, content, evidence_state=None,
        document_type=None):
    metadata = {
        "source": source, "category": category,
        "document_type": document_type or "unknown",
        "content_hash": chunk_id.split(":")[0],
    }
    if evidence_state is not None:
        metadata["evidence_state"] = evidence_state
    return RetrievedDocument(
        content=content, score=0.5, source=source, metadata=metadata,
        strategy="vector", chunk_id=chunk_id, rank=1,
    )


def shipped_context():
    """One verified evidence document: a real publishing opportunity."""
    return [
        doc("evidence/backend/fastapi.md", category="evidence",
            chunk_id="a1b2c3:0", content=EVIDENCE_TEXT,
            evidence_state="VERIFIED"),
    ]


def weak_context():
    """One learning-state course document: weak material, honestly labeled."""
    return [
        doc("courses/distributed.md", category="in_progress_courses",
            chunk_id="cc0011:0", content=COURSE_TEXT,
            evidence_state="LEARNING"),
    ]


class FakeReasoner:
    """The LLM reasoning boundary: answers from a script, remembers calls."""

    name = "eval-reasoner"
    prompt_version = "eval-reasoner-v1"

    def __init__(self, answer=None, *, error=None):
        self.answer = answer or ReasoningAnswer(
            publish=False, decline_reason="nothing here is worth publishing"
        )
        self.error = error
        self.calls = 0

    def reason(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.answer


def publish_answer():
    return ReasoningAnswer(
        publish=True, topic="evidence",
        angle="What building this taught me about API design",
        project="shipment-api", evidence_labels=("E1",), strategy=None,
        rationale="the work is recent and the evidence states it plainly",
        decline_reason="",
    )


def weak_answer():
    return ReasoningAnswer(
        publish=True, topic="in_progress_courses",
        angle="What the course is teaching me", project=None,
        evidence_labels=("E1",), strategy=None,
        rationale="keeping a public learning log",
        decline_reason="",
    )


class FakeLLM:
    """The model boundary: scripted replies, real exceptions on demand."""

    def __init__(self, replies=(), *, error=None):
        self.replies = list(replies)
        self.error = error
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        reply = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return SimpleNamespace(content=reply)


def generation_reply(post, evidence_used=("E1",)):
    return json.dumps({
        "post": post, "evidence_used": list(evidence_used),
        "declined": False, "reason": "",
    })


class FakeJudge:
    """The advisory-judge boundary: supports everything, or explodes."""

    name = "eval-judge"
    prompt_version = "eval-judge-v1"

    def __init__(self, *, error=None):
        self.error = error
        self.calls = 0

    def judge(self, request):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return tuple(
            JudgeVerdict(claim_index=claim.index, supported=True, reason="")
            for claim in request.claims
        )


class FakeLinkedIn:
    """Stands in for ``publish_to_linkedin``: records calls, never dials."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, text):
        self.calls.append(text)
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def linkedin_result(outcome, *, post_id=None, message="fake LinkedIn answer",
                    category=None, retryable=False, requires_human=False,
                    http_status=None):
    return PublicationResult(
        outcome=outcome, message=message, api_version="202607",
        attempted_at=to_iso(utc_now()), http_status=http_status,
        post_id=post_id, error_category=category, retryable=retryable,
        requires_human_intervention=requires_human,
    )


class FakeHttp:
    """Fake HTTP callables under the *real* ``publish_to_linkedin``.

    Lets a scenario exercise the genuine Step 5 classification (timeouts,
    expiry) with zero packets: ``get``/``post`` answer from a script, and any
    unexpected call raises loudly.
    """

    def __init__(self, *, get=None, post=None):
        self.get_answer = get
        self.post_answer = post
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if isinstance(self.get_answer, BaseException):
            raise self.get_answer
        assert self.get_answer is not None, "unexpected LinkedIn GET"
        return self.get_answer

    def post(self, url, **kwargs):
        self.calls.append(("POST", url))
        if isinstance(self.post_answer, BaseException):
            raise self.post_answer
        assert self.post_answer is not None, "unexpected LinkedIn POST"
        return self.post_answer


def _http_response(status, *, body="", headers=None):
    built = requests.Response()
    built.status_code = status
    built._content = body.encode()
    built.headers.update(headers or {})
    return built


def _identity(sub="abc123"):
    return _http_response(200, body=json.dumps({"sub": sub}),
                          headers={"Content-Type": "application/json"})


def _unsigned_id_token(issued_at):
    claims = json.dumps({"iat": int(issued_at.timestamp())}).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def expired_credential(path):
    """A credential file that expired an hour ago. Never leaves the disk.

    Issued two hours ago with a one-hour lifetime, so the recorded expiry
    stays internally consistent (``expires_at >= issued_at``): the Step 1
    CHECK rightly rejects fixtures that claim issuance after expiry.
    """
    issued = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    path.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": "expired-access-token",
        "expires_in": 3600,
        "scope": "email,openid,profile,w_member_social",
        "id_token": _unsigned_id_token(issued),
    }
    target = path / "linkedin_tokens.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(target, (NOW.timestamp(), NOW.timestamp()))
    return target


class FakeMail:
    """The email boundary: captures deliveries, sends nothing."""

    name = "fake-mail"

    def __init__(self):
        self.sent = []
        self.recipient = "user@example.invalid"

    def describe(self):
        return "fake-mail"

    def send(self, message):
        self.sent.append(message)


class FailingMail(FakeMail):
    """The email boundary, down: every delivery raises, deterministically."""

    def send(self, message):
        raise NotificationDeliveryError(
            NotificationFailureCategory.TRANSPORT, "smtp refused delivery"
        )


# ----------------------------------------------------------------- harnesses ---

def _chroma(base, embeddings):
    from langchain_chroma import Chroma

    return Chroma(
        collection_name="eval_kb",
        embedding_function=embeddings,
        persist_directory=str(base / "chroma"),
    )


def _chroma_texts(chroma):
    result = chroma.get(include=["documents"])
    return list(result["documents"])


def _sync_config(base, registry, mail, chroma, embeddings):
    """A sync workflow over the real pipeline and a temporary collection."""
    store_path = base / "state.db"

    def sync_fn(reg, store):
        from app.sync import SyncContext, sync_all

        return sync_all(
            reg, SyncContext(store=store, chroma=chroma,
                             embeddings=embeddings)
        )

    return SyncConfig(
        store_factory=lambda: StateStore(store_path),
        registry_loader=lambda: registry,
        sync_fn=sync_fn,
        notifier_factory=lambda s: NotificationService(s, transport=mail),
    )


def _registry(base, *sources):
    return Registry(sources=tuple(sources), path=base / "sources.yaml")


def _publish_request(agent_result):
    """The Step 11 request translation, for injecting a fake transport."""
    proposal = agent_result.proposal
    refs = tuple(
        evidence_ref(item.source, item.chunk_id)
        for item in (proposal.evidence if proposal is not None else ())
    )
    return PublishRequest(
        content=agent_result.draft.content,
        topic=proposal.topic if proposal is not None else None,
        angle=proposal.angle if proposal is not None else None,
        project=proposal.project if proposal is not None else None,
        evidence=refs,
    )


def _branding_config(base, documents, *, reasoner, llm, judge,
                     transport, mail, history=None):
    """A branding run with the real Agent, generator, verifier, publisher,
    and notifier — fakes only at the external boundaries."""
    store_path = base / "state.db"

    def assemble(store):
        return build_context(RetrievalResult(
            query="evaluation topic", strategy="vector",
            documents=list(documents), diagnostics={},
        ), store)

    def make_agent(store):
        return BrandingAgent(
            reasoner=reasoner,
            generator=PostGenerator(llm=llm),
            verifier=EvidenceVerifier(judge=judge),
            history=(PublishingHistory(store) if history is None
                     else history),
        )

    def publish_fn(agent_result, run_id, store):
        service = PublishingService(store, transport=transport)
        return service.publish(_publish_request(agent_result), run_id)

    return BrandingConfig(
        store_factory=lambda: StateStore(store_path),
        assemble_fn=assemble,
        agent_factory=make_agent,
        publish_fn=publish_fn,
        notifier_factory=lambda s: NotificationService(s, transport=mail),
    )


def _run_row(base, run_id):
    with StateStore(base / "state.db") as store:
        return store.get_run(run_id)


def _phases(base, run_id):
    with StateStore(base / "state.db") as store:
        return [(p.phase, p.outcome) for p in store.list_phases(run_id)]


def _failures(base, run_id=None):
    with StateStore(base / "state.db") as store:
        return store.list_failures(run_id=run_id)


def _dead_pid():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


# ----------------------------------------------------------------- scenarios ---
#
# Each scenario drives a real workflow boundary from a clean isolated state
# and returns its recorded outcome plus the state the assertions need. The
# focused tests below assert the details; the milestone asserts the outcome
# vector across the whole set, twice.

def scenario_no_change_sync(base, make_git_repo, make_source):
    """An unchanged source performs no work on the second pass."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nSteady words.\n")
    head = repo.commit()
    registry = _registry(
        base, make_source(repo.path, name="alpha", ref="main"))
    mail = FakeMail()
    cfg = _sync_config(base, registry, mail, chroma, embeddings)

    first = run_sync(cfg)
    count_after_first = len(_chroma_texts(chroma))
    second = run_sync(cfg)

    with StateStore(base / "state.db") as store:
        checkpoint = store.get_checkpoint("alpha")
    return {
        "outcome": second.outcome,
        "first": first.outcome,
        "counts": (count_after_first, len(_chroma_texts(chroma))),
        "checkpoint": checkpoint.last_revision if checkpoint else None,
        "head": head,
        "phases": _phases(base, second.run_id),
        "failures": _failures(base, second.run_id),
        "emails": len(mail.sent),
        "run_id": second.run_id,
    }


def scenario_changed_git_source(base, make_git_repo, make_source):
    """A new commit is picked up, ingested, and checkpointed."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nSteady words.\n")
    repo.commit()
    registry = _registry(
        base, make_source(repo.path, name="alpha", ref="main"))
    mail = FakeMail()
    cfg = _sync_config(base, registry, mail, chroma, embeddings)

    first = run_sync(cfg)
    repo.write("b.md", "# Beta\n\nUNIQUEBETATEXT joins the base.\n")
    head = repo.commit()
    second = run_sync(cfg)

    with StateStore(base / "state.db") as store:
        checkpoint = store.get_checkpoint("alpha")
    texts = _chroma_texts(chroma)
    return {
        "outcome": second.outcome,
        "first": first.outcome,
        "checkpoint": checkpoint.last_revision if checkpoint else None,
        "head": head,
        "new_present": any("UNIQUEBETATEXT" in text for text in texts),
        "phases": _phases(base, second.run_id),
        "failures": _failures(base, second.run_id),
        "emails": len(mail.sent),
        "run_id": second.run_id,
    }


def scenario_completed_project_new_commit(base, make_git_repo, make_source):
    """A COMPLETED project with new activity is synced and flagged."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nSteady words.\n")
    repo.commit()
    active = _registry(
        base, make_source(repo.path, name="alpha", ref="main",
                           lifecycle=LifecycleState.ACTIVE))
    mail = FakeMail()
    first = run_sync(_sync_config(base, active, mail, chroma, embeddings))

    repo.write("c.md", "# Gamma\n\nUNIQUEGAMMATEXT after completion.\n")
    repo.commit()
    completed = _registry(
        base, make_source(repo.path, name="alpha", ref="main",
                           lifecycle=LifecycleState.COMPLETED))
    second = run_sync(_sync_config(base, completed, mail, chroma, embeddings))

    texts = _chroma_texts(chroma)
    return {
        "outcome": second.outcome,
        "first": first.outcome,
        "failed_phase": second.failed_phase,
        "new_present": any("UNIQUEGAMMATEXT" in text for text in texts),
        "phases": _phases(base, second.run_id),
        "failures": [(f.phase, f.error_category, f.requires_human_intervention)
                     for f in _failures(base, second.run_id)],
        "emails": len(mail.sent),
        "run_id": second.run_id,
    }


def scenario_deleted_file(base, make_git_repo, make_source):
    """A deleted file's vectors leave the collection on the next pass."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nSteady words.\n")
    repo.write("b.md", "# Beta\n\nUNIQUEREMOVABLETEXT here.\n")
    repo.commit()
    registry = _registry(
        base, make_source(repo.path, name="alpha", ref="main"))
    mail = FakeMail()
    cfg = _sync_config(base, registry, mail, chroma, embeddings)

    first = run_sync(cfg)
    repo.remove("b.md")
    head = repo.commit()
    second = run_sync(cfg)

    with StateStore(base / "state.db") as store:
        checkpoint = store.get_checkpoint("alpha")
    texts = _chroma_texts(chroma)
    return {
        "outcome": second.outcome,
        "first": first.outcome,
        "checkpoint": checkpoint.last_revision if checkpoint else None,
        "head": head,
        "removed_gone": not any("UNIQUEREMOVABLETEXT" in t for t in texts),
        "kept_present": any("Steady words" in t for t in texts),
        "phases": _phases(base, second.run_id),
        "failures": _failures(base, second.run_id),
        "emails": len(mail.sent),
        "run_id": second.run_id,
    }


def _publishing_branding(base, *, documents, reasoner, llm, judge,
                         transport, mail):
    cfg = _branding_config(
        base, documents, reasoner=reasoner, llm=llm, judge=judge,
        transport=transport, mail=mail,
    )
    return run_branding(cfg), cfg


def scenario_normal_publication(base):
    """Verified evidence becomes exactly one published post."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:eval1",
        message="published to LinkedIn as urn:li:share:eval1",
    ))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
        intent = store.get_intent_for_run(result.run_id)
        evidence = (
            [(ref.source_path, ref.content_hash)
             for ref in store.get_publication(
                 publications[0].publication_id).evidence]
            if publications else []
        )
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "linkedin_calls": len(transport.calls),
        "publications": [
            (p.linkedin_post_id, p.outcome.value) for p in publications
        ],
        "intent_state": intent.state.value if intent else None,
        "evidence": evidence,
        "phases": _phases(base, result.run_id),
        "failures": _failures(base, result.run_id),
        "failure_emails": [m for m in mail.sent
                           if "issue" in m.body.lower()
                           or "failed" in m.body.lower()],
        "publication_emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_no_publication_opportunity(base):
    """The Agent declines; nothing is sent anywhere."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:never"))
    result, _ = _publishing_branding(
        base, documents=weak_context(),
        reasoner=FakeReasoner(), llm=FakeLLM([]), judge=FakeJudge(),
        transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
    return {
        "outcome": result.outcome,
        "linkedin_calls": len(transport.calls),
        "publications": len(publications),
        "phases": _phases(base, result.run_id),
        "failures": _failures(base, result.run_id),
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_duplicate_candidate(base):
    """An already-published text is refused before any request."""
    mail = FakeMail()
    seed_transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:seed"))
    with StateStore(base / "state.db") as store:
        seed_run = store.start_run(Workflow.BRANDING)
        service = PublishingService(store, transport=seed_transport)
        seed_report = service.publish(
            PublishRequest(content=PASSING_POST, topic="evidence"), seed_run.run_id)
        store.finish_run(seed_run.run_id, RunOutcome.DO_NOT_PUBLISH)

    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:dupe"))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
    return {
        "outcome": result.outcome,
        "seed_published": seed_report.published,
        "second_run_calls": len(transport.calls),
        "publications": len(publications),
        "refused": result.detail.get("refused", False),
        "phases": _phases(base, result.run_id),
        "failures": _failures(base, result.run_id),
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_weak_evidence(base):
    """Learning-state evidence cannot carry a mastery claim: no post."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:never"))
    result, _ = _publishing_branding(
        base, documents=weak_context(),
        reasoner=FakeReasoner(weak_answer()),
        llm=FakeLLM([generation_reply(WEAK_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
    return {
        "outcome": result.outcome,
        "reason": result.detail.get("no_publish_reason"),
        "linkedin_calls": len(transport.calls),
        "publications": len(publications),
        "phases": _phases(base, result.run_id),
        "failures": _failures(base, result.run_id),
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_generation_failure(base):
    """An unreachable model fails the decide phase; nothing is published."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:never"))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([], error=ConnectionError("model unreachable")),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "linkedin_calls": len(transport.calls),
        "publications": len(publications),
        "phases": _phases(base, result.run_id),
        "failures": [(f.phase, f.error_category) for f in
                     _failures(base, result.run_id)],
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_verification_failure(base):
    """A crashing advisory judge fails the gate closed: no verdict, no post."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:never"))

    class ExplodingJudge(FakeJudge):
        def judge(self, request):
            raise RuntimeError("judge crashed while judging")

    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=ExplodingJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "linkedin_calls": len(transport.calls),
        "publications": len(publications),
        "phases": _phases(base, result.run_id),
        "failures": [(f.phase, f.error_category) for f in
                     _failures(base, result.run_id)],
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def _real_publisher_transport(base, http, token_path):
    """The genuine Step 5 entry point over a fake HTTP layer (zero packets)."""
    from app.state.store import StateStore as _Store

    def transport(text):
        with _Store(base / "state.db") as store:
            return publish_to_linkedin(
                text, store=store,
                client=LinkedInClient(get=http.get, post=http.post,
                                      api_version="202607"),
                token_path=token_path, now=NOW,
            )

    return transport


def scenario_linkedin_timeout(base):
    """A read timeout after the request was sent is unknowable: escalate."""
    mail = FakeMail()
    http = FakeHttp(get=_identity(), post=requests.ReadTimeout("timed out"))
    transport = _real_publisher_transport(base, http, _valid_credential(base))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
        states = [p.outcome.value for p in publications]
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "http_posts": [c for c in http.calls if c[0] == "POST"],
        "publication_states": states,
        "phases": _phases(base, result.run_id),
        "failures": [(f.phase, f.requires_human_intervention) for f in
                     _failures(base, result.run_id)],
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def _valid_credential(base):
    """A credential file valid at NOW. Never leaves the temp directory."""
    base.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": "eval-access-token",
        "expires_in": 5183999,
        "scope": "email,openid,profile,w_member_social",
        "id_token": _unsigned_id_token(NOW),
    }
    target = base / "linkedin_tokens.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(target, (NOW.timestamp(), NOW.timestamp()))
    return target


def _unsigned_id_token(issued_at):
    claims = json.dumps({"iat": int(issued_at.timestamp())}).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=").decode()
    return f"header.{payload}.signature"


def scenario_ambiguous_publication(base):
    """UNKNOWN stays unknown: escalate once, then block the retry."""
    mail = FakeMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.UNKNOWN,
        message="LinkedIn accepted the request but returned no post id",
    ))
    first, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        states_after_first = [p.outcome.value
                              for p in store.list_publications()]

    second, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        states_after_second = [p.outcome.value
                               for p in store.list_publications()]
        first_notes = [n.delivery_state.value for n in
                       store.list_notifications(run_id=first.run_id)]
        second_notes = [n.delivery_state.value for n in
                        store.list_notifications(run_id=second.run_id)]
    return {
        "outcome": first.outcome,
        "second_outcome": second.outcome,
        "second_failed_phase": second.failed_phase,
        "external_attempts": len(transport.calls),
        "states_after_first": states_after_first,
        "states_after_second": states_after_second,
        "first_phases": _phases(base, first.run_id),
        "second_phases": _phases(base, second.run_id),
        "first_failures": [(f.phase, f.requires_human_intervention)
                           for f in _failures(base, first.run_id)],
        "emails": len(mail.sent),
        "first_notifications": first_notes,
        "second_notifications": second_notes,
        "run_id": first.run_id,
        "second_run_id": second.run_id,
    }


def scenario_token_expired(base):
    """An expired credential fails closed before any request: escalate."""
    mail = FakeMail()
    http = FakeHttp(
        get=AssertionError("no HTTP on an expired credential"),
        post=AssertionError("no HTTP on an expired credential"),
    )
    transport = _real_publisher_transport(base, http, expired_credential(base))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([generation_reply(PASSING_POST)]),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        publications = store.list_publications()
        states = [p.outcome.value for p in publications]
        messages = [(f.phase, f.message)
                    for f in store.list_failures(run_id=result.run_id)]
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "http_calls": list(http.calls),
        "publication_states": states,
        "failures": [(f.phase, f.error_category, f.requires_human_intervention)
                     for f in _failures(base, result.run_id)],
        "failure_messages": messages,
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_notification_delivery_failure(base):
    """A dead mailbox does not rewrite the workflow failure it carries."""
    mail = FailingMail()
    transport = FakeLinkedIn(linkedin_result(
        PublicationOutcome.PUBLISHED, post_id="urn:li:share:never"))
    result, _ = _publishing_branding(
        base, documents=shipped_context(),
        reasoner=FakeReasoner(publish_answer()),
        llm=FakeLLM([], error=ConnectionError("model unreachable")),
        judge=FakeJudge(), transport=transport, mail=mail,
    )
    with StateStore(base / "state.db") as store:
        run = store.get_run(result.run_id)
        failures = store.list_failures(run_id=result.run_id)
        deliveries = store.list_notifications(run_id=result.run_id)
    return {
        "outcome": result.outcome,
        "stored_outcome": run.outcome,
        "failed_phase": result.failed_phase,
        "notified": result.notified,
        "failure_rows": [(f.phase, f.occurrence_count) for f in failures],
        "delivery_rows": [(n.delivery_state.value, n.error_message)
                          for n in deliveries],
        "run_id": result.run_id,
    }


def scenario_duplicate_scheduled_invocation(base, make_git_repo, make_source):
    """Two back-to-back invocations: one runs, one is rejected."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    repo = make_git_repo()
    repo.write("a.md", "# Alpha\n\nSteady words.\n")
    repo.commit()
    registry = _registry(
        base, make_source(repo.path, name="alpha", ref="main"))
    mail = FakeMail()

    with StateStore(base / "state.db") as store:
        store.acquire_lock(lock_name_for(Workflow.SYNC),
                           "eval-scheduler:1:first0001", 3600.0)
    locked = None
    try:
        run_sync(_sync_config(base, registry, mail, chroma, embeddings))
    except WorkflowLocked as exc:
        locked = exc
    with StateStore(base / "state.db") as store:
        assert store.release_lock(lock_name_for(Workflow.SYNC),
                                  "eval-scheduler:1:first0001")
    result = run_sync(_sync_config(base, registry, mail, chroma, embeddings))

    with StateStore(base / "state.db") as store:
        runs = store.list_runs()
        rejections = [f for f in store.list_failures()
                      if f.phase == "lock"]
    return {
        "outcome": result.outcome,
        "locked": locked is not None,
        "runs": [(r.workflow, r.outcome) for r in runs],
        "rejections": [(f.error_category, f.run_id) for f in rejections],
        "phases": _phases(base, result.run_id),
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_recovery_after_interrupted_run(base):
    """A SIGKILL aftermath — stale lock, unfinished run, silent intent —
    is reclaimed, reported, and never resolved into a false outcome."""
    import socket as _socket

    mail = FakeMail()
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    with StateStore(base / "state.db") as store:
        crashed = store.start_run(Workflow.BRANDING)
        store.record_phase(crashed.run_id, "context", "ok")
        intent = store.create_publish_intent(
            crashed.run_id, "half-written words", topic="t")
        store.acquire_lock(lock_name_for(Workflow.BRANDING),
                           f"{_socket.gethostname()}:{child.pid}:crashed0001",
                           0)
    time.sleep(0.02)

    result, _ = _publishing_branding(
        base, documents=weak_context(),
        reasoner=FakeReasoner(), llm=FakeLLM([]), judge=FakeJudge(),
        transport=FakeLinkedIn(linkedin_result(
            PublicationOutcome.PUBLISHED, post_id="urn:li:share:never")),
        mail=mail,
    )
    with StateStore(base / "state.db") as store:
        old = store.get_run(crashed.run_id)
        kept_intent = store.get_publish_intent(intent.intent_id)
        recoveries = [f for f in store.list_failures()
                      if f.error_category == "stale_lock_recovered"]
        interruptions = [f for f in store.list_failures()
                         if f.error_category == "interrupted_run"]
        lock = store.get_lock(lock_name_for(Workflow.BRANDING))
    return {
        "outcome": result.outcome,
        "old_outcome": old.outcome,
        "intent_state": kept_intent.state,
        "recoveries": len(recoveries),
        "interruptions": [(f.dedupe_key, f.run_id) for f in interruptions],
        "lock_released": lock is None,
        "phases": _phases(base, result.run_id),
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_self_ingestion_attempt(base, make_source):
    """A source rooted inside the application is refused, never ingested."""
    from app.sources.enums import SourceType as _ST

    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    source = make_source(PROJECT_ROOT, name="self", type=_ST.FILESYSTEM,
                         ref=None, include=("**/*",))
    mail = FakeMail()
    result = run_sync(
        _sync_config(base, _registry(base, source), mail, chroma,
                     embeddings))

    texts = _chroma_texts(chroma)
    with StateStore(base / "state.db") as store:
        source_rows = [(f.error_category, f.requires_human_intervention,
                        f.run_id)
                       for f in store.list_failures(limit=100)]
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "indexed": len(texts),
        "phases": _phases(base, result.run_id),
        "failures": [(f.phase, f.error_category, f.requires_human_intervention)
                     for f in _failures(base, result.run_id)],
        "source_rows": source_rows,
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


def scenario_unregistered_source_path_missing(base, make_source):
    """A registered-but-missing path is a reported failure, never a skip."""
    embeddings = FakeEmbeddings()
    chroma = _chroma(base, embeddings)
    source = make_source(base / "gone", name="gone")
    mail = FakeMail()
    result = run_sync(
        _sync_config(base, _registry(base, source), mail, chroma,
                     embeddings))
    with StateStore(base / "state.db") as store:
        source_rows = [(f.error_category, f.requires_human_intervention,
                        f.run_id)
                       for f in store.list_failures(limit=100)]
    return {
        "outcome": result.outcome,
        "failed_phase": result.failed_phase,
        "phases": _phases(base, result.run_id),
        "failures": [(f.phase, f.error_category, f.requires_human_intervention)
                     for f in _failures(base, result.run_id)],
        "source_rows": source_rows,
        "emails": len(mail.sent),
        "run_id": result.run_id,
    }


SCENARIOS = (
    ("no-change sync", scenario_no_change_sync, RunOutcome.DO_NOT_PUBLISH),
    ("changed Git source", scenario_changed_git_source,
     RunOutcome.DO_NOT_PUBLISH),
    ("completed project with new commit",
     scenario_completed_project_new_commit,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
    ("deleted file", scenario_deleted_file, RunOutcome.DO_NOT_PUBLISH),
    ("normal publication", scenario_normal_publication,
     RunOutcome.DO_NOT_PUBLISH),
    ("no publication opportunity", scenario_no_publication_opportunity,
     RunOutcome.DO_NOT_PUBLISH),
    ("duplicate candidate", scenario_duplicate_candidate,
     RunOutcome.DO_NOT_PUBLISH),
    ("weak evidence", scenario_weak_evidence, RunOutcome.DO_NOT_PUBLISH),
    ("generation failure", scenario_generation_failure,
     RunOutcome.WORKFLOW_FAILED),
    ("verification failure", scenario_verification_failure,
     RunOutcome.WORKFLOW_FAILED),
    ("LinkedIn timeout", scenario_linkedin_timeout,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
    ("ambiguous publication", scenario_ambiguous_publication,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
    ("token expired", scenario_token_expired,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
    ("notification delivery failure",
     scenario_notification_delivery_failure, RunOutcome.WORKFLOW_FAILED),
    ("duplicate scheduled invocation",
     scenario_duplicate_scheduled_invocation, RunOutcome.DO_NOT_PUBLISH),
    ("recovery after interrupted run",
     scenario_recovery_after_interrupted_run, RunOutcome.DO_NOT_PUBLISH),
    ("self-ingestion attempt", scenario_self_ingestion_attempt,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
    ("unregistered source path missing",
     scenario_unregistered_source_path_missing,
     RunOutcome.REQUIRES_HUMAN_INTERVENTION),
)


# --------------------------------------------------------------------- tests ---

def test_no_change_sync_is_a_quiet_success(tmp_path, make_git_repo,
                                           make_source):
    report = scenario_no_change_sync(tmp_path, make_git_repo, make_source)

    assert report["first"] is RunOutcome.DO_NOT_PUBLISH
    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    before, after = report["counts"]
    assert before > 0 and after == before
    assert report["checkpoint"] == report["head"]
    assert report["phases"] == [("load_registry", "ok"),
                                ("synchronize", "ok")]
    assert report["failures"] == []
    assert report["emails"] == 0
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.DO_NOT_PUBLISH)


def test_changed_git_source_is_ingested_and_checkpointed(
        tmp_path, make_git_repo, make_source):
    report = scenario_changed_git_source(tmp_path, make_git_repo, make_source)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["checkpoint"] == report["head"]
    assert report["new_present"] is True
    assert report["failures"] == []
    assert report["emails"] == 0


def test_completed_project_with_new_commit_needs_a_person(
        tmp_path, make_git_repo, make_source):
    report = scenario_completed_project_new_commit(tmp_path, make_git_repo,
                                                   make_source)

    assert report["first"] is RunOutcome.DO_NOT_PUBLISH
    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["failed_phase"] == "synchronize"
    # The signal is an addition to synchronization, never a substitute:
    # the new content was still ingested.
    assert report["new_present"] is True
    assert any(human for _, _, human in report["failures"])
    assert report["emails"] == 1
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.REQUIRES_HUMAN_INTERVENTION)


def test_deleted_file_is_purged_from_the_collection(
        tmp_path, make_git_repo, make_source):
    report = scenario_deleted_file(tmp_path, make_git_repo, make_source)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["checkpoint"] == report["head"]
    assert report["removed_gone"] is True
    assert report["kept_present"] is True
    assert report["failures"] == []
    assert report["emails"] == 0


def test_normal_publication_publishes_exactly_once(tmp_path):
    report = scenario_normal_publication(tmp_path)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["failed_phase"] is None
    assert report["linkedin_calls"] == 1
    assert report["publications"] == [("urn:li:share:eval1", "published")]
    assert report["intent_state"] == PublishState.PUBLISHED.value
    assert report["evidence"] == [("evidence/backend/fastapi.md", "a1b2c3")]
    assert report["phases"] == [("context", "ok"), ("decide", "ok"),
                                ("publish", "ok")]
    assert report["failures"] == []
    assert report["failure_emails"] == []
    assert report["publication_emails"] == 1
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.DO_NOT_PUBLISH)


def test_no_publication_opportunity_sends_nothing(tmp_path):
    report = scenario_no_publication_opportunity(tmp_path)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["linkedin_calls"] == 0
    assert report["publications"] == 0
    assert report["phases"] == [("context", "ok"), ("decide", "ok")]
    assert report["failures"] == []
    assert report["emails"] == 0


def test_duplicate_candidate_is_refused_before_any_request(tmp_path):
    report = scenario_duplicate_candidate(tmp_path)

    assert report["seed_published"] is True
    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["refused"] is True
    assert report["second_run_calls"] == 0
    assert report["publications"] == 1
    assert report["failures"] == []
    assert report["emails"] == 0


def test_weak_evidence_prefers_no_post(tmp_path):
    report = scenario_weak_evidence(tmp_path)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["reason"] == "gate_rejected"
    assert report["linkedin_calls"] == 0
    assert report["publications"] == 0
    assert report["emails"] == 0


def test_generation_failure_fails_the_decide_phase(tmp_path):
    report = scenario_generation_failure(tmp_path)

    assert report["outcome"] is RunOutcome.WORKFLOW_FAILED
    assert report["failed_phase"] == "decide"
    assert report["linkedin_calls"] == 0
    assert report["publications"] == 0
    assert ("decide", "llm_unavailable") in report["failures"]
    assert report["emails"] == 1
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.WORKFLOW_FAILED)


def test_verification_failure_fails_closed(tmp_path):
    report = scenario_verification_failure(tmp_path)

    assert report["outcome"] is RunOutcome.WORKFLOW_FAILED
    assert report["failed_phase"] == "decide"
    assert report["linkedin_calls"] == 0
    assert report["publications"] == 0
    assert any(phase == "decide" for phase, _ in report["failures"])
    assert report["emails"] == 1


def test_linkedin_timeout_escalates_without_retry(tmp_path):
    report = scenario_linkedin_timeout(tmp_path)

    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["failed_phase"] == "publish"
    assert len(report["http_posts"]) == 1
    assert report["publication_states"] == ["unknown_requires_review"]
    assert any(human for _, human in report["failures"])
    assert report["emails"] == 1


def test_ambiguous_publication_never_double_publishes(tmp_path):
    report = scenario_ambiguous_publication(tmp_path)

    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["second_outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["second_failed_phase"] == "publish"
    assert report["external_attempts"] == 1
    assert report["states_after_first"] == ["unknown_requires_review"]
    assert report["states_after_second"] == ["unknown_requires_review"]
    # The guard records its own refusal: the phase exists, marked failed.
    assert report["second_phases"] == [("context", "ok"), ("decide", "ok"),
                                       ("publish", "failed")]
    assert any(human for _, human in report["first_failures"])
    # Each escalated run notifies exactly once: two runs, two notifications,
    # one external attempt. "Exactly once" is per run, not per incident.
    assert report["emails"] == 2
    assert report["first_notifications"] == ["sent"]
    assert report["second_notifications"] == ["sent"]
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.REQUIRES_HUMAN_INTERVENTION)


def test_token_expired_fails_closed_before_any_request(tmp_path):
    report = scenario_token_expired(tmp_path)

    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["failed_phase"] == "publish"
    assert report["http_calls"] == []
    assert report["publication_states"] == ["failed"]
    # The workflow records its own escalation category; the authentication
    # detail rides in the recorded failure message, and no request ran.
    assert ("publish", "publication_needs_review", True) in report["failures"]
    assert any("expired" in message
               for _, message in report["failure_messages"])
    assert report["emails"] == 1


def test_notification_delivery_failure_preserves_the_workflow_outcome(
        tmp_path):
    report = scenario_notification_delivery_failure(tmp_path)

    assert report["outcome"] is RunOutcome.WORKFLOW_FAILED
    assert report["stored_outcome"] is RunOutcome.WORKFLOW_FAILED
    assert report["failed_phase"] == "decide"
    assert report["notified"] is False
    assert report["failure_rows"] == [("decide", 1)]
    assert len(report["delivery_rows"]) == 1
    state, _message = report["delivery_rows"][0]
    assert state == DeliveryState.FAILED.value


def test_duplicate_scheduled_invocation_runs_once(tmp_path, make_git_repo,
                                                  make_source):
    report = scenario_duplicate_scheduled_invocation(tmp_path, make_git_repo,
                                                     make_source)

    assert report["locked"] is True
    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["runs"] == [("sync", RunOutcome.DO_NOT_PUBLISH)]
    assert report["rejections"] == [("lock_held", None)]
    assert report["phases"] == [("load_registry", "ok"),
                                ("synchronize", "ok")]
    assert report["emails"] == 0


def test_locked_invocation_exits_locked_without_running(monkeypatch):
    """The command wrapper maps a lockout to its distinct exit status."""
    from app.workflows import sync as sync_module

    def raise_locked(*_args, **_kwargs):
        raise WorkflowLocked("workflow:sync", "h:1:t", "already running")

    monkeypatch.setattr(sync_module, "run_sync", raise_locked)
    assert sync_module.main([]) == EXIT_LOCKED
    assert EXIT_LOCKED == 3


def test_recovery_after_interrupted_run(tmp_path):
    report = scenario_recovery_after_interrupted_run(tmp_path)

    assert report["outcome"] is RunOutcome.DO_NOT_PUBLISH
    assert report["old_outcome"] is None
    assert report["intent_state"] is PublishState.INTENT_CREATED
    assert report["recoveries"] == 1
    assert len(report["interruptions"]) == 1
    dedupe_key, run_id = report["interruptions"][0]
    assert dedupe_key is not None and run_id is None
    assert report["lock_released"] is True
    assert report["phases"] == [("context", "ok"), ("decide", "ok")]
    assert report["emails"] == 0


def test_self_ingestion_attempt_is_refused(tmp_path, make_source):
    report = scenario_self_ingestion_attempt(tmp_path, make_source)

    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["failed_phase"] == "synchronize"
    assert report["indexed"] == 0
    # The workflow records its aggregate; the sync layer records the refusal
    # itself, run-detached, exactly per the Step 3 contract.
    assert ("synchronize", "synchronize_needs_review", True) in report[
        "failures"]
    assert ("guard_refused", True, None) in report["source_rows"]
    assert report["emails"] == 1
    assert _run_row(tmp_path, report["run_id"]).outcome is (
        RunOutcome.REQUIRES_HUMAN_INTERVENTION)


def test_unregistered_source_path_missing_is_reported(tmp_path, make_source):
    report = scenario_unregistered_source_path_missing(tmp_path, make_source)

    assert report["outcome"] is RunOutcome.REQUIRES_HUMAN_INTERVENTION
    assert report["failed_phase"] == "synchronize"
    assert ("synchronize", "synchronize_needs_review", True) in report[
        "failures"]
    assert ("source_unavailable", True, None) in report["source_rows"]
    assert report["emails"] == 1


# ----------------------------------------------------------------- milestone ---

def _run_all_scenarios(base, make_git_repo, make_source):
    """The full set from a clean state: name -> recorded outcome."""
    outcomes = {}
    outcomes["no-change sync"] = scenario_no_change_sync(
        base / "s01", make_git_repo, make_source)["outcome"]
    outcomes["changed Git source"] = scenario_changed_git_source(
        base / "s02", make_git_repo, make_source)["outcome"]
    outcomes["completed project with new commit"] = (
        scenario_completed_project_new_commit(
            base / "s03", make_git_repo, make_source)["outcome"])
    outcomes["deleted file"] = scenario_deleted_file(
        base / "s04", make_git_repo, make_source)["outcome"]
    outcomes["normal publication"] = scenario_normal_publication(
        base / "s05")["outcome"]
    outcomes["no publication opportunity"] = (
        scenario_no_publication_opportunity(base / "s06")["outcome"])
    outcomes["duplicate candidate"] = scenario_duplicate_candidate(
        base / "s07")["outcome"]
    outcomes["weak evidence"] = scenario_weak_evidence(
        base / "s08")["outcome"]
    outcomes["generation failure"] = scenario_generation_failure(
        base / "s09")["outcome"]
    outcomes["verification failure"] = scenario_verification_failure(
        base / "s10")["outcome"]
    outcomes["LinkedIn timeout"] = scenario_linkedin_timeout(
        base / "s11")["outcome"]
    outcomes["ambiguous publication"] = scenario_ambiguous_publication(
        base / "s12")["outcome"]
    outcomes["token expired"] = scenario_token_expired(
        base / "s13")["outcome"]
    outcomes["notification delivery failure"] = (
        scenario_notification_delivery_failure(base / "s14")["outcome"])
    outcomes["duplicate scheduled invocation"] = (
        scenario_duplicate_scheduled_invocation(
            base / "s15", make_git_repo, make_source)["outcome"])
    outcomes["recovery after interrupted run"] = (
        scenario_recovery_after_interrupted_run(base / "s16")["outcome"])
    outcomes["self-ingestion attempt"] = scenario_self_ingestion_attempt(
        base / "s17", make_source)["outcome"]
    outcomes["unregistered source path missing"] = (
        scenario_unregistered_source_path_missing(
            base / "s18", make_source)["outcome"])
    return outcomes


EXPECTED_OUTCOMES = {
    "no-change sync": RunOutcome.DO_NOT_PUBLISH,
    "changed Git source": RunOutcome.DO_NOT_PUBLISH,
    "completed project with new commit":
        RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    "deleted file": RunOutcome.DO_NOT_PUBLISH,
    "normal publication": RunOutcome.DO_NOT_PUBLISH,
    "no publication opportunity": RunOutcome.DO_NOT_PUBLISH,
    "duplicate candidate": RunOutcome.DO_NOT_PUBLISH,
    "weak evidence": RunOutcome.DO_NOT_PUBLISH,
    "generation failure": RunOutcome.WORKFLOW_FAILED,
    "verification failure": RunOutcome.WORKFLOW_FAILED,
    "LinkedIn timeout": RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    "ambiguous publication": RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    "token expired": RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    "notification delivery failure": RunOutcome.WORKFLOW_FAILED,
    "duplicate scheduled invocation": RunOutcome.DO_NOT_PUBLISH,
    "recovery after interrupted run": RunOutcome.DO_NOT_PUBLISH,
    "self-ingestion attempt": RunOutcome.REQUIRES_HUMAN_INTERVENTION,
    "unregistered source path missing":
        RunOutcome.REQUIRES_HUMAN_INTERVENTION,
}


def test_milestone_full_scenario_set_is_deterministic(
        tmp_path, make_git_repo, make_source):
    """Every scenario, twice, from clean isolated state: same outcomes."""
    assert [name for name, _, _ in SCENARIOS] == list(EXPECTED_OUTCOMES)

    first = _run_all_scenarios(tmp_path / "run-a", make_git_repo, make_source)
    second = _run_all_scenarios(tmp_path / "run-b", make_git_repo, make_source)

    assert first == EXPECTED_OUTCOMES
    assert second == EXPECTED_OUTCOMES
    assert first == second
