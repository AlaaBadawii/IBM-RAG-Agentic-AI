"""The evaluation rubric: named metrics and the hard safety gates.

The rubric is versioned and reviewed. It is deliberately *not* editable by the
evaluator: the runner reads it, computes against it, and can never write it.
Metrics are kept separate rather than collapsed into one score, so a content
improvement can never compensate for a regression in factual grounding.

Safety metrics are **hard gates**. A run whose gate fails is a failed run
regardless of how good the editorial metrics look.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Versioned identifier of the metric definitions and gate policy. Bump when
#: the meaning of a metric or the gate changes.
RUBRIC_VERSION = "content-rubric-v1"

#: Metric names. Presented separately; never summed.
DECISION_SCHEMA_VALID_RATE = "decision_schema_valid_rate"
CITATION_RESOLUTION_RATE = "citation_resolution_rate"
VERIFICATION_PASS_RATE = "verification_pass_rate"
FORBIDDEN_INFERENCE_RATE = "forbidden_inference_rate"
UNSUPPORTED_REFERENCE_RATE = "unsupported_reference_rate"
INSUFFICIENT_EVIDENCE_HANDLING_RATE = "insufficient_evidence_handling_rate"
MALFORMED_HANDLING_RATE = "malformed_handling_rate"
SELECTION_AGREEMENT_RATE = "selection_agreement_rate"
#: Agreement between the pipeline's publish/no-publish decision and the reviewed
#: expected decision, over every scored case. It is not a quality judgement of
#: the draft, only whether the pipeline decided to publish when the review did.
PUBLISH_DECISION_AGREEMENT_RATE = "publish_decision_agreement_rate"

#: Metrics that are hard gates: the run is invalid if any of them regresses.
#: These describe factual grounding and publication safety, not editorial
#: quality, and must never be traded against the metrics above them.
HARD_GATE_METRICS: tuple[str, ...] = (
    FORBIDDEN_INFERENCE_RATE,
    UNSUPPORTED_REFERENCE_RATE,
)


@dataclass(frozen=True)
class EvaluationRubric:
    """The reviewed metric set and gate policy for one evaluation."""

    version: str = RUBRIC_VERSION
    metrics: tuple[str, ...] = (
        DECISION_SCHEMA_VALID_RATE,
        CITATION_RESOLUTION_RATE,
        VERIFICATION_PASS_RATE,
        FORBIDDEN_INFERENCE_RATE,
        UNSUPPORTED_REFERENCE_RATE,
        INSUFFICIENT_EVIDENCE_HANDLING_RATE,
        MALFORMED_HANDLING_RATE,
        SELECTION_AGREEMENT_RATE,
        PUBLISH_DECISION_AGREEMENT_RATE,
    )
    hard_gates: tuple[str, ...] = HARD_GATE_METRICS
    notes: tuple[str, ...] = field(default_factory=tuple)

    def is_hard_gate(self, metric_name: str) -> bool:
        return metric_name in self.hard_gates


def default_rubric() -> EvaluationRubric:
    """The rubric this stage evaluates against."""
    return EvaluationRubric()
