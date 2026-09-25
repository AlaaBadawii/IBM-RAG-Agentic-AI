"""The operational-state isolation boundary, pinned as tests.

The suite-wide fixture in ``tests/conftest.py`` (``isolated_operational_state``)
redirects default state opens to throwaway locations and fails loudly on any
direct reach for production. These tests prove each layer of that boundary;
without them the invariant would rest on the fixture existing rather than on
anything asserting it holds.
"""
import sqlite3

import pytest

from app import paths as app_paths
from app.state.store import StateStore
from tests.conftest import PRODUCTION_CHROMA_DIR, PRODUCTION_DB_PATH


def test_default_store_points_at_isolated_state_not_production():
    """A ``StateStore()`` built the way production code builds one lands in
    test state under pytest, never in the production file."""
    with StateStore() as store:
        assert store.path != PRODUCTION_DB_PATH
        assert store.path.parent != PRODUCTION_DB_PATH.parent


def test_explicit_production_db_open_is_a_hard_failure():
    """Accidental production access raises instead of opening silently."""
    with pytest.raises(AssertionError, match="production state database"):
        StateStore(PRODUCTION_DB_PATH)


def test_mutations_in_tests_cannot_reach_production(isolated_operational_state):
    """Writes through the default test store are absent from the real file."""
    marker = "isolation-canary"
    with StateStore() as store:
        store.set_source_lifecycle(marker, "PAUSED", note="canary")

    with sqlite3.connect(str(PRODUCTION_DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT source_name FROM source_lifecycle WHERE source_name = ?",
            (marker,),
        ).fetchall()
    assert rows == []


def test_production_configuration_is_unchanged(isolated_operational_state):
    """The boundary redirects the store module, not production config."""
    assert app_paths.STATE_DB_PATH == PRODUCTION_DB_PATH
    assert app_paths.CHROMA_DIR == PRODUCTION_CHROMA_DIR
    import app.state.store as store_module

    assert store_module.STATE_DB_PATH == isolated_operational_state[
        "isolated_db"]


def test_production_chroma_open_is_a_hard_failure():
    """A collection persisted under the production directory raises."""
    from langchain_chroma import Chroma

    from tests.conftest import FakeEmbeddings

    with pytest.raises(AssertionError, match="production Chroma"):
        Chroma(
            collection_name="isolation-canary",
            embedding_function=FakeEmbeddings(),
            persist_directory=str(PRODUCTION_CHROMA_DIR),
        )


def test_network_egress_is_blocked():
    """A test that reached for the network fails here, loudly."""
    import socket

    with pytest.raises(AssertionError, match="network egress is blocked"):
        socket.socket().connect(("example.invalid", 80))


def test_production_database_file_is_intact():
    """The real store opens read-only with a contiguous applied history.

    Read through raw sqlite — not ``StateStore``, which would migrate — so
    this assertion itself can never be the mutation it guards against.
    Contiguity (not an exact version) is asserted because production may
    legitimately lag the code by migrations nothing has applied yet.
    """
    from app.state import SCHEMA_VERSION

    with sqlite3.connect(f"file:{PRODUCTION_DB_PATH}?mode=ro",
                         uri=True) as conn:
        versions = [row[0] for row in conn.execute(
            "SELECT version FROM schema_version ORDER BY version")]
    assert versions == list(range(1, max(versions) + 1))
    assert max(versions) <= SCHEMA_VERSION
