"""Step 14: operational documentation consistency.

Proves the documented system matches the built system: every promised
document exists, the ADR index matches its files, the scheduler
configuration invokes real entry points without masking, and no real secret
material appears anywhere under ``docs/``. Fully offline.
"""
import importlib
import re
from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT

DOCS = PROJECT_ROOT / "docs"
ADRS = DOCS / "decisions" / "ADRs"

PROMISED_OPERATIONS = (
    "environment.md",
    "local-development.md",
    "security.md",
    "scheduling.md",
    "state-model.md",
    "recovery.md",
    "deployment.md",
    "publishing.md",
)

PROMISED_EVALUATION = (
    "autonomous-evaluation.md",
    "manual-linkedin.md",
    "quality-gates.md",
)

# Real key material, not family mentions (``sk-proj-…``) or placeholders
# (``<YOUR_…>``, ``[REDACTED]``, ``fake-*``). Each pattern requires a run of
# key characters after the prefix, which documentation prose never has.
SECRET_PATTERNS = (
    r"sk-proj-[A-Za-z0-9]{8,}",
    r"sk-or-v1-[A-Za-z0-9\-_]{8,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"gho_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[bap]-[A-Za-z0-9\-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
)


def test_every_promised_operations_document_exists():
    operations = DOCS / "operations"
    for name in PROMISED_OPERATIONS:
        assert (operations / name).is_file(), f"missing {name}"


def test_every_promised_evaluation_document_exists():
    evaluation = DOCS / "evaluation"
    for name in PROMISED_EVALUATION:
        assert (evaluation / name).is_file(), f"missing {name}"


def test_phases_cover_what_the_adr_index_references():
    phases = DOCS / "phases"
    assert (phases / "phase-01-foundation.md").is_file()
    assert (phases / "phase-02-ingestion.md").is_file()
    assert (phases / "phase-10-observability-memory.md").is_file()
    assert (phases / "README.md").is_file()


def test_adr_index_matches_adr_files():
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    indexed = set(re.findall(r"\| (ADR-\d+) \|", index))
    files = {path.stem.replace("adr-", "ADR-")
             for path in ADRS.glob("adr-*.md")}
    assert indexed, "ADR index names no ADRs"
    assert files, "no ADR files exist"
    assert indexed == files, (
        f"indexed without files: {sorted(indexed - files)}; "
        f"files without index: {sorted(files - indexed)}"
    )


def test_adr_referenced_paths_exist():
    """Every ``see `path` `` target in the ADR index resolves."""
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    targets = set(re.findall(r"see `([^`]+)`", index))
    assert targets, "ADR index references nothing"
    for target in targets:
        first = target.split(",")[0].strip()
        resolved = (ADRS / first).resolve()
        assert resolved.exists(), f"ADR references missing {first}"


def test_cron_entries_are_valid_and_unmasked():
    """The committed schedule parses and invokes real entry points."""
    lines = [
        line.strip()
        for line in (PROJECT_ROOT / "ops" / "personal-branding-agent.cron"
                     ).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        and "=" not in line.split()[0]
    ]
    assert len(lines) == 2
    modules = set()
    for line in lines:
        fields = line.split()
        assert len(fields) >= 6, f"not a cron entry: {line}"
        minute, hour, day, month, weekday = fields[:5]
        for field, allowed in (
            minute, r"[\d\*,/\-]+"), (hour, r"[\d\*,/\-]+"):
            assert re.fullmatch(allowed, field), f"bad schedule field: {line}"
        assert day == month == weekday == "*", f"unexpected date field: {line}"
        command = " ".join(fields[5:])
        assert "|| true" not in command and "; exit 0" not in command
        module = re.search(r"app\.workflows\.(sync|branding)\b", command)
        assert module, f"no workflow entry point: {line}"
        modules.add(module.group(1))
    assert modules == {"sync", "branding"}
    for module in ("app.workflows.sync", "app.workflows.branding"):
        imported = importlib.import_module(module)
        assert callable(imported.main)


def test_no_real_secrets_in_documentation():
    """Key families and placeholders are fine; key material is not."""
    offenders = []
    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            for match in re.finditer(pattern, text):
                offenders.append(f"{path.name}: {match.group(0)[:24]}…")
    assert offenders == [], f"secret material in docs: {offenders}"


def test_secret_paths_are_gitignored():
    """The commit boundary from the security posture, verified."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", ".env", "Auth_handling/linkedin_tokens.json",
         "state_db/", "chroma_db/", "logs/"],
        cwd=str(PROJECT_ROOT), check=True, capture_output=True, text=True,
    )
    assert tracked.stdout.strip() == "", (
        f"secret/runtime paths tracked: {tracked.stdout.strip()}"
    )
