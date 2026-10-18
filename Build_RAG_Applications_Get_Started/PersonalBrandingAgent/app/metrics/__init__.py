"""Publication engagement metrics: a hand-imported, decision-free report.

There is no metrics API binding and this system makes no live external calls,
so post performance is brought in deliberately, by hand, from a platform
export — and only to be *read* by a person. Nothing here feeds a decision the
pipeline makes, and nothing here writes to any table but
``publication_metrics``.

:mod:`app.metrics.import_metrics` is the safe path: it parses a CSV into
validated rows, checks every referenced publication exists, and defaults to a
dry run so a mistake changes nothing.
"""
from app.metrics.import_metrics import (
    MetricRow,
    apply_plan,
    main,
    parse_metrics_csv,
)

__all__ = [
    "MetricRow",
    "apply_plan",
    "main",
    "parse_metrics_csv",
]
