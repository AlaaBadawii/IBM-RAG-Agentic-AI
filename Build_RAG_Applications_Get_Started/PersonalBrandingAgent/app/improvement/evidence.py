"""Read-only evidence collection from an explicit database copy.

The collector never touches the authoritative store. It snapshots a database
the caller names, using SQLite's online backup API, into a private directory,
then reads that copy in read-only mode. The source file is opened
``mode=ro``, so even the snapshot cannot write to it; the backup API is used
rather than a file copy because a live SQLite file copied naively can be torn.

What it deliberately does *not* do:

* import :mod:`app.state.store` or construct a ``StateStore`` — opening the
  production store can run migrations;
* read the schema version from a code constant — it reads the recorded
  ``schema_version`` ledger and validates the copy it is holding;
* export drafts, credentials, tokens, notification bodies or any field not on
  the explicit allowlists below.

Absent historical information stays absent. The collector does not reconstruct
prompts, model settings, drafts, claims or verdicts that were never recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

#: The newest recorded schema version this collector understands. Read from the
#: copy's own ``schema_version`` ledger and compared here; a copy from the
#: future is refused rather than misread.
SUPPORTED_SCHEMA_VERSION = 13

#: Explicit column allowlists. Anything not named here is never exported, so a
#: later schema that adds a secret-bearing column cannot leak through a
#: ``SELECT *``. Draft text (``publish_intents.content``), notification bodies,
#: and every credential table are intentionally absent.
EXPORT_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "workflow_runs": (
        "run_id", "workflow", "outcome", "started_at", "finished_at",
    ),
    "publications": (
        "publication_id", "run_id", "outcome", "content_hash", "recorded_at",
    ),
    "publication_evidence": (
        "publication_id", "source_path", "content_hash",
    ),
    "content_opportunities": (
        "opportunity_id", "topic", "project", "status", "attempts",
        "last_decision", "evidence_strength", "snapshot_version",
    ),
    "opportunity_outcomes": (
        "run_id", "opportunity_id", "topic", "decision", "selected_count",
    ),
}


class EvidenceError(RuntimeError):
    """Evidence could not be collected safely or was not understood."""


@dataclass(frozen=True)
class EvidenceBundle:
    """The result of one collection: where it came from and what it holds."""

    source_path: str
    copy_path: str
    schema_version: int
    exports: dict[str, str] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    tables_available: tuple[str, ...] = ()
    tables_unavailable: tuple[str, ...] = ()
    created_at: str | None = None

    def total_rows(self) -> int:
        return sum(self.counts.values())

    def as_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "copy_path": self.copy_path,
            "schema_version": self.schema_version,
            "exports": dict(self.exports),
            "counts": dict(self.counts),
            "hashes": dict(self.hashes),
            "tables_available": list(self.tables_available),
            "tables_unavailable": list(self.tables_unavailable),
            "created_at": self.created_at,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_database(source: Path | str, dest: Path | str) -> Path:
    """Copy ``source`` to ``dest`` with SQLite's backup API, read-only source.

    The source connection is ``mode=ro``, so this cannot mutate the
    authoritative file or leave a WAL behind. ``dest`` is created with owner-only
    permissions.
    """
    source = Path(source)
    dest = Path(dest)
    if not source.is_file():
        raise EvidenceError(f"source database not found: {source}")
    if source.resolve() == dest.resolve():
        raise EvidenceError("source and destination are the same file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30)
        dst = sqlite3.connect(str(dest), timeout=30)
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
            dst.close()
    except sqlite3.Error as exc:  # pragma: no cover - defensive
        raise EvidenceError(f"could not snapshot {source}: {exc}") from exc
    os.chmod(dest, 0o600)
    return dest


def open_read_only(path: Path | str) -> sqlite3.Connection:
    """Open a SQLite file strictly read-only. Never creates or migrates."""
    path = Path(path)
    if not path.is_file():
        raise EvidenceError(f"database copy not found: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def recorded_schema_version(conn: sqlite3.Connection) -> int:
    """The copy's *recorded* schema version, read from its ledger.

    Deliberately not a code constant: the whole point is to learn what the copy
    actually is. Raises if the ledger is absent or empty.
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) AS v FROM schema_version"
        ).fetchone()
    except sqlite3.Error as exc:
        raise EvidenceError(
            f"no schema_version ledger in the supplied copy: {exc}"
        ) from exc
    if row is None or row["v"] is None:
        raise EvidenceError("the supplied copy recorded no schema version")
    return int(row["v"])


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _export_table(conn: sqlite3.Connection, table: str,
                  columns: tuple[str, ...]) -> list[dict]:
    present = _table_columns(conn, table)
    if not present:
        raise EvidenceError(f"table {table} is absent from the copy")
    selected = tuple(c for c in columns if c in present)
    if not selected:
        return []
    sql = f"SELECT {', '.join(selected)} FROM {table}"
    return [dict(r) for r in conn.execute(sql)]


def collect_evidence(source_db: Path | str, dest_dir: Path | str, *,
                     created_at: str | None = None) -> EvidenceBundle:
    """Snapshot ``source_db`` and export only the allowlisted fields.

    Returns an :class:`EvidenceBundle`. Whether an individual table was present
    is recorded in ``tables_available`` / ``tables_unavailable`` so a caller can
    tell "not exported" from "did not exist".
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(dest_dir, 0o700)

    copy_path = snapshot_database(source_db, dest_dir / "evidence.db")
    conn = open_read_only(copy_path)
    try:
        version = recorded_schema_version(conn)
        if version > SUPPORTED_SCHEMA_VERSION:
            raise EvidenceError(
                f"copy records schema version {version}, newer than the "
                f"collector supports ({SUPPORTED_SCHEMA_VERSION})"
            )
        available: list[str] = []
        unavailable: list[str] = []
        exports: dict[str, str] = {}
        counts: dict[str, int] = {}
        hashes: dict[str, str] = {}
        for table, columns in EXPORT_ALLOWLIST.items():
            try:
                rows = _export_table(conn, table, columns)
            except EvidenceError:
                unavailable.append(table)
                continue
            out_path = dest_dir / f"{table}.jsonl"
            with open(out_path, "w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, sort_keys=True))
                    fh.write("\n")
            os.chmod(out_path, 0o600)
            available.append(table)
            exports[table] = str(out_path)
            counts[table] = len(rows)
            hashes[table] = _sha256_file(out_path)
    finally:
        conn.close()

    return EvidenceBundle(
        source_path=str(Path(source_db)),
        copy_path=str(copy_path),
        schema_version=version,
        exports=exports,
        counts=counts,
        hashes=hashes,
        tables_available=tuple(sorted(available)),
        tables_unavailable=tuple(sorted(unavailable)),
        created_at=created_at,
    )
