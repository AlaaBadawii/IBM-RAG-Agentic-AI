"""Behavioural tests for the source registry, its guard, and its lifecycle.

Three themes, matching the three ways this layer can hurt the knowledge base:

*What is admitted.* A source's include list is a floor and its exclusions are a
veto, so a file enters the corpus only when a pattern deliberately said so.
Several tests here check the boundaries of that rule rather than its happy
path — a directory pattern must reach the files inside it, and `Agent/` must
not match `AgentX/`, because both mistakes are silent.

*What must never be admitted.* The application's own source, its runtime state,
and its credentials are the sharpest hazard in the registry (``PLAN.md`` §5.3),
so they are guarded twice and tested twice: structurally by
:func:`is_protected`, and against the committed ``sources.yaml`` itself.

*What a lifecycle declaration may change.* Never visibility. The tests below
assert that no disposition can skip a source and that activity in a
``COMPLETED`` project is both ingested and surfaced.
"""
from pathlib import Path

import pytest

from app.errors import RegistryError
from app.paths import PROJECT_ROOT
from app.sources import (
    PROTECTED_ROOT,
    SourceDefinition,
    SourceType,
    SyncDisposition,
    SyncPriority,
    assert_path_admissible,
    is_protected,
    load_registry,
    looks_like_credential,
    plan_for,
    probes_admitted_by,
    protected_probes,
    review_signal_for,
    sanitize_repo_url,
    validate_registry,
)
from app.sources.patterns import PatternError, is_admitted, matches
from app.sources.registry import MAX_SCAN_DEPTH, is_virtualenv, scan_source_tree
from app.state.enums import LifecycleState

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

MINIMAL_DEFAULTS = """\
defaults:
  exclude:
    - pattern: "**/.git/"
      reason: "object store"
    - pattern: "**/venv/"
      reason: "virtual environment"
"""


def write_registry(tmp_path: Path, sources_yaml: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text(sources_yaml, encoding="utf-8")
    return path


def make_dir(tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def make_repo(tmp_path: Path, name: str) -> Path:
    """A directory that looks like a git checkout to the path check."""
    target = make_dir(tmp_path, name)
    (target / ".git").mkdir(exist_ok=True)
    return target


def filesystem_entry(name: str, path: Path, include: str = '"**/*.md"', extra: str = "") -> str:
    return (
        f"  - name: {name}\n"
        f"    type: filesystem\n"
        f"    local_path: {path}\n"
        f"    lifecycle: ACTIVE\n"
        f"    include: [{include}]\n"
        f"{extra}"
    )


def registry_with(tmp_path: Path, body: str) -> Path:
    return write_registry(tmp_path, "version: 1\n" + MINIMAL_DEFAULTS + "sources:\n" + body)


# --------------------------------------------------------------------------
# Patterns: the floor and the veto
# --------------------------------------------------------------------------


class TestAdmission:
    def test_empty_include_admits_nothing(self):
        """A source with no include pattern is silent, not permissive.

        This is the half of the rule that is easy to get backwards: an empty
        include could reasonably mean "everything", and meaning instead
        "nothing" is what forces every source to state its purpose.
        """
        assert is_admitted("app/main.py", (), ("**/*.md",)) is False

    def test_include_is_a_floor_not_a_suggestion(self):
        assert is_admitted("notes.md", ("**/*.md",), ()) is True
        assert is_admitted("main.py", ("**/*.md",), ()) is False

    def test_deny_wins_over_include(self):
        """An exclusion beats an include that would otherwise admit the file.

        Last-rule-wins would make this depend on the order rules happen to be
        written in; deny-wins makes it depend only on which rules exist.
        """
        assert is_admitted(".env", ("**/*",), ("**/.env",)) is False

    def test_directory_pattern_reaches_files_inside_it(self):
        # A virtualenv is only excluded if excluding its directory also
        # excludes the hundreds of modules within it.
        assert matches("a/venv/lib/mod.py", "**/venv/") is True
        assert is_admitted("a/venv/lib/mod.py", ("**/*.py",), ("**/venv/",)) is False

    def test_directory_pattern_respects_the_component_boundary(self):
        """`Agent/` must not match `AgentX/` — a substring match would."""
        assert matches("Agent/x.py", "Agent/") is True
        assert matches("AgentX/x.py", "Agent/") is False

    def test_extensionless_and_literal_names(self):
        # ALX names its shell scripts without extensions, and Dockerfile has
        # no extension at all; both are authored work.
        assert matches("0-hello_world", "**/*") is True
        assert matches("a/b/Dockerfile", "**/Dockerfile") is True
        assert matches("Dockerfile.dev", "**/Dockerfile") is False

    def test_bare_filename_matches_at_any_depth(self):
        assert matches("deep/nested/notes.md", "notes.md") is True

    def test_unsupported_syntax_is_rejected_rather_than_approximated(self):
        """A pattern the matcher cannot honour must fail, not match loosely.

        Character classes are the case: silently treating `[abc]` as a
        literal would make an exclusion that never excludes anything, and
        nothing downstream would report it.
        """
        with pytest.raises(PatternError):
            matches("a.py", "**/*.[py]")


# --------------------------------------------------------------------------
# The self-ingestion guard
# --------------------------------------------------------------------------


class TestSelfIngestionGuard:
    def test_application_directory_is_protected(self):
        assert is_protected(PROJECT_ROOT / "app" / "main.py") is True
        assert is_protected(PROTECTED_ROOT / "sources.yaml") is True

    def test_paths_outside_the_application_are_not_protected(self):
        assert is_protected("/home/someone/else/project/main.py") is False

    def test_a_sibling_with_a_shared_prefix_is_not_protected(self):
        """`PersonalBrandingAgentX` is not inside `PersonalBrandingAgent`."""
        assert is_protected(PROJECT_ROOT.parent / (PROJECT_ROOT.name + "X")) is False

    def test_a_symlink_cannot_launder_access_to_the_application(self, tmp_path):
        """The guard resolves symlinks, so a link is refused as well as a path.

        Without this, a source could exclude the real directory and still
        reach it through a link that only looks like it points elsewhere.
        """
        link = tmp_path / "innocent"
        link.symlink_to(PROJECT_ROOT)
        assert is_protected(link) is True
        assert is_protected(link / "sources.yaml") is True

    def test_assert_path_admissible_names_the_offending_source(self):
        with pytest.raises(RegistryError) as excinfo:
            assert_path_admissible("my-source", PROJECT_ROOT / "config.py")
        assert "my-source" in str(excinfo.value)

    def test_probes_admitted_by_is_empty_for_an_unrelated_root(self, tmp_path):
        assert probes_admitted_by(tmp_path, ("**/*",), ()) == []

    def test_probes_admitted_by_reports_the_leaks_a_registry_would_cause(self):
        """The check that catches a missing exclusion, before any file is read."""
        leaks = probes_admitted_by(PROJECT_ROOT.parent, ("**/*",), ())
        assert leaks, "a source rooted above the application must not admit all of it"
        assert any(leak.endswith("sources.yaml") for leak in leaks)

    def test_probe_set_covers_credentials_and_runtime_state(self):
        probes = protected_probes()
        for expected in (".env", "Auth_handling/linkedin_tokens.json", "chroma_db/chroma.sqlite3"):
            assert expected in probes


# --------------------------------------------------------------------------
# The committed registry itself
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def committed_registry():
    """Loaded once: it walks every source tree, and it never varies per test."""
    return load_registry()


class TestCommittedRegistry:
    """Asserts against sources.yaml — the artifact that actually ships."""

    def test_loads_and_validates(self, committed_registry):
        assert len(committed_registry) > 0
        validate_registry(committed_registry)

    def test_every_source_path_exists(self, committed_registry):
        missing = [str(s.local_path) for s in committed_registry if not s.local_path.is_dir()]
        assert missing == []

    def test_names_are_unique(self, committed_registry):
        assert len(set(committed_registry.names)) == len(committed_registry.names)

    def test_no_source_can_ingest_the_application(self, committed_registry):
        """The acceptance test for PLAN.md §5.3 hazard 1.

        Run against the real file with the real patterns, because the guard
        that matters is the one the synchronizer will actually consult.
        """
        offenders = {}
        for source in committed_registry:
            leaks = probes_admitted_by(
                source.local_path, source.include, source.exclude_patterns
            )
            if leaks:
                offenders[source.name] = leaks
        assert offenders == {}, f"these sources would ingest the application: {offenders}"

    def test_no_declared_root_is_a_filesystem_source(self, committed_registry):
        roots = {root.resolve() for root in committed_registry.declared_roots}
        offenders = [
            s.name for s in committed_registry if not s.is_git and s.local_path.resolve() in roots
        ]
        assert offenders == []

    def test_nothing_not_registered_is_also_registered(self, committed_registry):
        registered = {s.local_path.resolve() for s in committed_registry}
        overlap = [
            str(entry.path) for entry in committed_registry.not_registered
            if entry.path.resolve() in registered
        ]
        assert overlap == []

    def test_every_git_source_names_a_repository_and_a_ref(self, committed_registry):
        for source in committed_registry:
            if source.is_git:
                assert source.repo_identity, f"{source.name} has no repo_identity"
                assert source.ref, f"{source.name} has no ref"

    def test_no_committed_identity_carries_a_credential(self, committed_registry):
        """The committed_registry is committed; remote URLs in the workspace are not.

        Fourteen inspected repositories embed a token in their local git
        remote, so copying one verbatim into this file would publish a
        credential. This is the test that keeps that from happening.
        """
        for source in committed_registry:
            if source.repo_identity:
                assert not looks_like_credential(source.repo_identity), source.name
                assert source.repo_identity == sanitize_repo_url(source.repo_identity)

    def test_the_application_is_not_among_the_sources(self, committed_registry):
        assert not any(p.name == PROJECT_ROOT.name and p == PROJECT_ROOT for p in
                       (s.local_path for s in committed_registry))

    def test_the_registry_is_not_its_own_source(self, committed_registry):
        assert "sources.yaml" not in {s.local_path.name for s in committed_registry}

    def test_covers_exactly_the_periodic_sync_scope(self, committed_registry):
        """Periodic sync covers the five roots the user named — no more.

        ``sync_all`` iterates this registry and nothing else, so this exact
        set *is* the periodic sync scope: ~/LLMs (IBM, AI_Agents, AI_Hackthon
        sources), ~/Quizey, ~/DevOps, ~/DataBases, and
        ~/DSA-Python-LeetCode-130. ~/ALX, ~/FastAPI and ~/Portfolio are
        deliberately outside it.
        """
        assert set(committed_registry.names) == {
            "ibm-genai-coursework",
            "ai-agents",
            "hackathon-lectures",
            "hackathon-practice-lab",
            "quizey-v2",
            "quizey-platform",
            "jenkins-practice",
            "kodekloud-devops-specialization",
            "devops-lab",
            "kubernetes-lab",
            "databases-mongodb-crud",
            "dsa-python-leetcode-130",
        }

    def test_the_third_party_ibm_template_is_registered_nowhere(self, committed_registry):
        """Style_Finder is IBM's course template, not the user's work."""
        assert "Style_Finder" not in " ".join(committed_registry.names)
        assert any(
            "Style_Finder" in str(entry.path) for entry in committed_registry.not_registered
        )

    def test_every_exclusion_states_a_reason(self, committed_registry):
        for source in committed_registry:
            for rule in source.exclude:
                assert rule.reason.strip(), f"{source.name}: {rule.pattern} has no reason"


# --------------------------------------------------------------------------
# Loading and validation failures
# --------------------------------------------------------------------------


class TestRegistryRefusals:
    """Every one of these must stop the load rather than drop an entry.

    A registry that loads with a source silently missing produces no error and
    no signal — just a knowledge base that quietly stops covering part of the
    user's work. Failing loudly is the only safe direction.
    """

    def test_rejects_a_source_whose_path_does_not_exist(self, tmp_path):
        body = filesystem_entry("ghost", tmp_path / "does-not-exist")
        with pytest.raises(RegistryError, match="ghost"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_git_source_that_is_not_a_repository(self, tmp_path):
        target = make_dir(tmp_path, "plain")
        body = (
            "  - name: not-really-git\n"
            "    type: git\n"
            f"    local_path: {target}\n"
            "    repo_identity: https://example.com/x.git\n"
            "    ref: main\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="not-really-git"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_filesystem_source_that_is_a_repository(self, tmp_path):
        target = make_repo(tmp_path, "actually-git")
        with pytest.raises(RegistryError, match="actually-git"):
            load_registry(registry_with(tmp_path, filesystem_entry("actually-git", target)))

    def test_rejects_a_git_source_without_a_repo_identity(self, tmp_path):
        target = make_repo(tmp_path, "anon")
        body = (
            "  - name: anon\n"
            "    type: git\n"
            f"    local_path: {target}\n"
            "    ref: main\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="repo_identity"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_git_source_without_a_ref(self, tmp_path):
        target = make_repo(tmp_path, "noref")
        body = (
            "  - name: noref\n"
            "    type: git\n"
            f"    local_path: {target}\n"
            "    repo_identity: https://example.com/x.git\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="ref"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_filesystem_source_with_revision_fields(self, tmp_path):
        target = make_dir(tmp_path, "plain2")
        body = (
            "  - name: plain2\n"
            "    type: filesystem\n"
            f"    local_path: {target}\n"
            "    repo_identity: https://example.com/x.git\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="plain2"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_an_empty_include(self, tmp_path):
        target = make_dir(tmp_path, "silent")
        body = (
            "  - name: silent\n"
            "    type: filesystem\n"
            f"    local_path: {target}\n"
            "    lifecycle: ACTIVE\n"
            "    include: []\n"
        )
        with pytest.raises(RegistryError, match="silent"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_an_exclusion_without_a_reason(self, tmp_path):
        target = make_dir(tmp_path, "why")
        body = filesystem_entry(
            "why", target, extra='    exclude:\n      - pattern: "**/*.tmp"\n'
        )
        with pytest.raises(RegistryError, match="reason"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_malformed_pattern(self, tmp_path):
        target = make_dir(tmp_path, "badpat")
        body = filesystem_entry("badpat", target, include='"**/*.[py]"')
        with pytest.raises(RegistryError, match="badpat"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_an_unknown_lifecycle_value(self, tmp_path):
        target = make_dir(tmp_path, "weird")
        body = (
            "  - name: weird\n"
            "    type: filesystem\n"
            f"    local_path: {target}\n"
            "    lifecycle: FINISHED\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="lifecycle"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_duplicate_names(self, tmp_path):
        target = make_dir(tmp_path, "dup")
        body = filesystem_entry("same", target) + filesystem_entry("same", target)
        with pytest.raises(RegistryError, match="duplicate"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_plain_directory_root_taken_as_a_source(self, tmp_path):
        """The rule the workspace forced us to sharpen: a root that is a plain
        directory is a place to look, not something to ingest."""
        target = make_dir(tmp_path, "rootish")
        body = (
            "workspace_roots:\n"
            f"  - path: {target}\n"
            "sources:\n" + filesystem_entry("rootish", target)
        )
        with pytest.raises(RegistryError, match="declared workspace root"):
            load_registry(write_registry(tmp_path, "version: 1\n" + MINIMAL_DEFAULTS + body))

    def test_allows_a_repository_rooted_at_a_declared_root(self, tmp_path):
        """A repository at a declared root is one revision history — one source.

        `~/LLMs/IBM` is both a declared root and a single repository that
        contains this application, so the rule cannot be "a root is never a
        source" without exception.
        """
        target = make_repo(tmp_path, "reporoot")
        body = (
            "workspace_roots:\n"
            f"  - path: {target}\n"
            "sources:\n"
            "  - name: reporoot\n"
            "    type: git\n"
            f"    local_path: {target}\n"
            "    repo_identity: https://example.com/r.git\n"
            "    ref: main\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        registry = load_registry(
            write_registry(tmp_path, "version: 1\n" + MINIMAL_DEFAULTS + body)
        )
        assert registry.names == ("reporoot",)

    def test_rejects_a_nested_repository_left_unaccounted_for(self, tmp_path):
        """A repository inside a source must be named or excluded, never swept."""
        outer = make_repo(tmp_path, "outer")
        inner = outer / "inner"
        inner.mkdir()
        (inner / ".git").mkdir()
        with pytest.raises(RegistryError, match="nested"):
            load_registry(registry_with(tmp_path, filesystem_entry("outer", outer)))

    def test_rejects_an_unexcluded_virtualenv_inside_a_source(self, tmp_path):
        """A virtualenv's modules would otherwise match `**/*.py`."""
        source = make_dir(tmp_path, "withvenv")
        venv = source / "my_env"          # unconventional name, on purpose
        venv.mkdir()
        (venv / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
        body = filesystem_entry("withvenv", source, include='"**/*.py"')
        with pytest.raises(RegistryError, match="virtual environment"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_not_registered_entry_that_is_also_a_source(self, tmp_path):
        target = make_dir(tmp_path, "both")
        body = (
            "sources:\n"
            + filesystem_entry("both", target)
            + "not_registered:\n"
            f"  - path: {target}\n"
            '    reason: "listed twice"\n'
        )
        with pytest.raises(RegistryError, match="both"):
            load_registry(write_registry(tmp_path, "version: 1\n" + MINIMAL_DEFAULTS + body))

    def test_rejects_a_credential_smuggled_into_a_repo_identity(self, tmp_path):
        target = make_repo(tmp_path, "leaky")
        body = (
            "  - name: leaky\n"
            "    type: git\n"
            f"    local_path: {target}\n"
            "    repo_identity: https://user:ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@github.com/u/r.git\n"
            "    ref: main\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.md"]\n'
        )
        with pytest.raises(RegistryError, match="leaky"):
            load_registry(registry_with(tmp_path, body))

    def test_rejects_a_source_that_would_admit_the_application(self, tmp_path, monkeypatch):
        """Validation consults the real application directory, not a fixture."""
        body = (
            "  - name: swallowing\n"
            "    type: git\n"
            f"    local_path: {PROJECT_ROOT.parent}\n"
            "    repo_identity: https://example.com/x.git\n"
            "    ref: main\n"
            "    lifecycle: ACTIVE\n"
            '    include: ["**/*.yml"]\n'
        )
        with pytest.raises(RegistryError, match="swallowing"):
            load_registry(registry_with(tmp_path, body))


# --------------------------------------------------------------------------
# Lifecycle: depth and priority, never visibility
# --------------------------------------------------------------------------


def _source(lifecycle: LifecycleState, name: str = "s") -> SourceDefinition:
    """A source with no patterns — lifecycle is all these tests exercise."""
    return SourceDefinition(
        name=name,
        type=SourceType.FILESYSTEM,
        local_path=Path("/tmp/s"),
        lifecycle=lifecycle,
    )


class TestLifecycle:
    def test_no_disposition_can_skip_a_source(self):
        """`ignore forever` is unrepresentable, not merely discouraged."""
        assert [d.value for d in SyncDisposition] == ["NORMAL", "REVIEW_REQUIRED"]

    def test_every_plan_ingests(self):
        for lifecycle in LifecycleState:
            plan = plan_for(_source(lifecycle), has_changes=True)
            assert plan.ingest is True, lifecycle

    def test_active_work_is_ingested_quietly_at_high_priority(self):
        plan = plan_for(_source(LifecycleState.ACTIVE), has_changes=True)
        assert plan.disposition is SyncDisposition.NORMAL
        assert plan.priority is SyncPriority.HIGH
        assert plan.needs_review is False

    def test_a_completed_project_with_new_commits_is_ingested_and_reviewed(self):
        """The case PLAN.md names: the declaration, not the change, is in doubt."""
        source = _source(LifecycleState.COMPLETED)
        plan = plan_for(source, has_changes=True)
        assert plan.ingest is True
        assert plan.disposition is SyncDisposition.REVIEW_REQUIRED
        assert plan.priority is SyncPriority.LOW

        signal = review_signal_for(source, ("src/new_feature.py",))
        assert signal is not None
        assert signal.lifecycle is LifecycleState.COMPLETED
        assert signal.changed_paths == ("src/new_feature.py",)
        assert "new_feature.py" in signal.as_message() or signal.changed_paths

    def test_paused_and_planned_also_review(self):
        for lifecycle in (LifecycleState.PAUSED, LifecycleState.PLANNED):
            signal = review_signal_for(_source(lifecycle), ("x.py",))
            assert signal is not None, lifecycle

    def test_an_unchanged_source_never_raises_a_signal(self):
        """Otherwise the signal becomes noise, and a gate nobody reads is not a gate."""
        for lifecycle in LifecycleState:
            plan = plan_for(_source(lifecycle), has_changes=False)
            assert plan.disposition is SyncDisposition.NORMAL
            assert review_signal_for(_source(lifecycle), ()) is None

    def test_an_active_source_with_changes_raises_no_signal(self):
        assert review_signal_for(_source(LifecycleState.ACTIVE), ("x.py",)) is None


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


class TestCredentialSanitization:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://AlaaBadawii:ghp_abc123@github.com/u/r.git", "https://github.com/u/r.git"),
            ("https://user:pass@github.com/u/r.git", "https://github.com/u/r.git"),
            ("https://github.com/u/r.git", "https://github.com/u/r.git"),
            ("git@github.com:AlaaBadawii/Quizey-V2.git", "git@github.com:AlaaBadawii/Quizey-V2.git"),
        ],
    )
    def test_userinfo_is_stripped_and_clean_urls_are_untouched(self, url, expected):
        assert sanitize_repo_url(url) == expected

    def test_sanitizing_is_idempotent(self):
        once = sanitize_repo_url("https://u:ghp_x@github.com/u/r.git")
        assert sanitize_repo_url(once) == once

    @pytest.mark.parametrize(
        "text",
        [
            "ghp_" + "a" * 36,
            "github_pat_" + "a" * 30,
            "sk-" + "a" * 40,
            "xoxb-1234567890-abcdefghij",
            "AKIAIOSFODNN7EXAMPLE",
            "-----BEGIN RSA PRIVATE KEY-----",
        ],
    )
    def test_recognises_credential_shapes(self, text):
        assert looks_like_credential(text) is True

    @pytest.mark.parametrize(
        "text",
        ["https://github.com/u/r.git", "git@github.com:u/r.git", "untracked: no remote"],
    )
    def test_ordinary_identities_are_not_flagged(self, text):
        assert looks_like_credential(text) is False


# --------------------------------------------------------------------------
# Tree scanning: nested repositories and virtualenvs
# --------------------------------------------------------------------------


class TestTreeScan:
    def test_virtualenv_detection_is_structural_not_namebased(self, tmp_path):
        """The workspace holds `.venv`, `venv`, `my_env` and `fastapi_venv`."""
        for name in (".venv", "venv", "my_env", "fastapi_venv"):
            env = tmp_path / name
            env.mkdir(exist_ok=True)
            (env / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
            assert is_virtualenv(env) is True, name

    def test_a_directory_that_is_not_a_virtualenv(self, tmp_path):
        plain = tmp_path / "src"
        plain.mkdir()
        assert is_virtualenv(plain) is False

    def test_scan_finds_a_nested_repository(self, tmp_path):
        root = tmp_path / "root"
        inner = root / "sub" / "inner"
        inner.mkdir(parents=True)
        (inner / ".git").mkdir()
        scan = scan_source_tree(root)
        assert inner in scan.nested_repositories

    def test_scan_does_not_report_the_root_as_nested_in_itself(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / ".git").mkdir()
        assert scan_source_tree(root).nested_repositories == ()

    def test_scan_reports_a_virtualenv_that_no_pattern_excludes(self, tmp_path):
        root = tmp_path / "root"
        env = root / "my_env"
        env.mkdir(parents=True)
        (env / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
        assert env in scan_source_tree(root).virtualenvs

    def test_scan_ignores_an_excluded_subtree(self, tmp_path):
        root = tmp_path / "root"
        inner = root / "vendored" / "dep"
        inner.mkdir(parents=True)
        (inner / ".git").mkdir()
        scan = scan_source_tree(root, ("vendored/",))
        assert scan.nested_repositories == ()

    def test_scan_fails_closed_rather_than_truncating_at_the_depth_cap(self, tmp_path):
        """A short list would be a false negative, which is the one forbidden answer."""
        root = tmp_path / "root"
        deep = root
        for i in range(MAX_SCAN_DEPTH + 2):
            deep = deep / f"d{i}"
            deep.mkdir(parents=True)
        with pytest.raises(RegistryError, match="depth limit"):
            scan_source_tree(root)

    def test_scan_reports_a_repository_nested_several_levels_down(self, tmp_path):
        root = tmp_path / "root"
        inner = root / "a" / "b" / "c"
        inner.mkdir(parents=True)
        (inner / ".git").mkdir()
        assert inner in scan_source_tree(root).nested_repositories
