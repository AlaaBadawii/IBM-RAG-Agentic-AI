"""Step 3: resolving revisions and detecting changed paths.

Two questions, tested separately because the whole design depends on their not
being confused: *what revision is the source at now* (this module), and *what
revision did the system successfully process* (the store, tested in
test_sync_synchronizer.py).
"""
import pytest

from app.errors import GitError, SourceUnavailableError, SyncError
from app.sources.enums import SourceType
from app.sync.enums import ChangeType, RevisionKind
from app.sync.revision import (
    CONTENT_REVISION_PREFIX,
    changed_paths,
    content_revision,
    is_known_commit,
    iter_admitted_files,
    read_admitted_paths,
    read_revision,
    resolve_git_revision,
)
from tests.conftest import PROJECT_ROOT, git


# ------------------------------------------------------ admitted inventory ---

def test_admitted_files_respects_include_and_is_sorted(tmp_path, make_source):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "notes.txt").write_text("not admitted")
    source = make_source(tmp_path)

    assert read_admitted_paths(source) == ("a.md", "b.md")


def test_admitted_files_skips_excluded_directories_entirely(tmp_path, make_source):
    """An exclusion prunes the walk, so a huge directory costs nothing."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.md").write_text("keep")
    (tmp_path / "node_modules" / "deep").mkdir(parents=True)
    (tmp_path / "node_modules" / "deep" / "vendored.py").write_text("vendored")
    source = make_source(tmp_path, exclude=(("node_modules/", "third-party code"),))

    assert read_admitted_paths(source) == ("src/keep.md",)


def test_admitted_files_never_leaves_the_source_through_a_symlink(
    tmp_path, make_source
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("not this source's content")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "real.md").write_text("real")
    (source_dir / "link.md").symlink_to(outside / "secret.md")

    source = make_source(source_dir)
    assert read_admitted_paths(source) == ("real.md",)


def test_a_source_cannot_reach_the_application_through_a_directory_symlink(
    tmp_path, make_source
):
    """The live monorepo case, in miniature.

    The committed registry's ``ibm-genai-coursework`` sits at an ancestor of
    this application, so a source's walk can reach the application's own
    directory without ever leaving its own root. The refusal has to be by
    resolved path and it has to happen while descending — refusing *after*
    reading the tree would mean walking ``.venv/`` and ``chroma_db/`` on every
    one of twenty-eight sources, every day.
    """
    root = tmp_path / "monorepo"
    root.mkdir()
    (root / "coursework").mkdir()
    (root / "coursework" / "notebook.md").write_text("# Coursework\n", encoding="utf-8")
    (root / PROJECT_ROOT.name).symlink_to(PROJECT_ROOT, target_is_directory=True)
    source = make_source(root, name="monorepo", type=SourceType.FILESYSTEM,
                         ref=None, include=("**/*",))

    admitted = read_admitted_paths(source)

    assert admitted == ("coursework/notebook.md",)
    assert not any(path.startswith(PROJECT_ROOT.name) for path in admitted)


def test_admitted_files_excludes_the_git_object_store(tmp_path, make_git_repo, make_source):
    repo = make_git_repo()
    repo.write("readme.md", "hello")
    repo.commit()
    source = make_source(repo.path, include=("**/*",))

    admitted = read_admitted_paths(source)
    assert "readme.md" in admitted
    assert not any(path.startswith(".git/") for path in admitted)


def test_unreadable_directory_is_an_error_not_an_empty_inventory(
    tmp_path, make_source
):
    """A partial walk would be a false claim about the source."""
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "hidden.md").write_text("x")
    locked.chmod(0o000)
    try:
        with pytest.raises(SyncError):
            iter_admitted_files(make_source(tmp_path))
    finally:
        locked.chmod(0o700)  # so pytest can clean up


# --------------------------------------------------------- content revision ---

def test_content_revision_is_stable_across_walks(tmp_path, make_source):
    (tmp_path / "a.md").write_text("one")
    (tmp_path / "b.md").write_text("two")
    source = make_source(tmp_path)

    assert content_revision(source) == content_revision(source)
    assert content_revision(source).startswith(CONTENT_REVISION_PREFIX)


def test_content_revision_changes_with_content(tmp_path, make_source):
    (tmp_path / "a.md").write_text("one")
    source = make_source(tmp_path)
    before = content_revision(source)

    (tmp_path / "a.md").write_text("two")
    assert content_revision(source) != before


def test_content_revision_changes_when_a_path_moves_though_content_does_not(
    tmp_path, make_source
):
    """Paths are in the digest: the stored key moved, so the index must follow."""
    (tmp_path / "a.md").write_text("identical bytes")
    source = make_source(tmp_path)
    before = content_revision(source)

    (tmp_path / "a.md").rename(tmp_path / "b.md")
    assert content_revision(source) != before


def test_content_revision_ignores_inadmissible_files(tmp_path, make_source):
    (tmp_path / "a.md").write_text("one")
    source = make_source(tmp_path)
    before = content_revision(source)

    (tmp_path / "ignored.txt").write_text("brand new, but not admitted")
    assert content_revision(source) == before


def test_content_revision_is_empty_safe(tmp_path, make_source):
    source = make_source(tmp_path)
    # The empty inventory has a digest, not an error: a registered source with
    # nothing admitted is a legitimate, if unusual, state.
    assert content_revision(source).startswith(CONTENT_REVISION_PREFIX)


# ------------------------------------------------------------ read_revision ---

def test_read_revision_filesystem_source_is_a_content_digest(tmp_path, make_source):
    (tmp_path / "a.md").write_text("one")
    source = make_source(tmp_path, type=SourceType.FILESYSTEM, ref=None)

    revision = read_revision(source)
    assert revision.kind is RevisionKind.CONTENT
    assert revision.revision == content_revision(source)


def test_read_revision_git_source_is_the_commit(tmp_path, make_git_repo, make_source):
    repo = make_git_repo()
    repo.write("a.md", "one")
    commit = repo.commit()

    revision = read_revision(make_source(repo.path))
    assert revision.kind is RevisionKind.GIT
    assert revision.revision == commit


def test_read_revision_follows_the_declared_ref(tmp_path, make_git_repo, make_source):
    repo = make_git_repo()
    repo.write("a.md", "one")
    first = repo.commit()
    git(repo.path, "checkout", "--quiet", "-b", "feature")
    repo.write("a.md", "two")
    repo.commit()

    on_main = read_revision(make_source(repo.path, ref="main"))
    on_feature = read_revision(make_source(repo.path, ref="feature"))
    assert on_main.revision == first
    assert on_feature.revision != first


def test_read_revision_git_repository_with_no_commits_falls_back_to_content(
    tmp_path, make_git_repo, make_source
):
    """A registered repository with an unborn HEAD is still synchronizable."""
    repo = make_git_repo()
    repo.write("a.md", "one")

    revision = read_revision(make_source(repo.path))
    assert revision.kind is RevisionKind.CONTENT
    assert "no commits" in revision.detail


def test_read_revision_missing_path_is_source_unavailable(tmp_path, make_source):
    with pytest.raises(SourceUnavailableError):
        read_revision(make_source(tmp_path / "gone"))


def test_read_revision_declared_git_but_not_a_repository(tmp_path, make_source):
    (tmp_path / "a.md").write_text("one")
    with pytest.raises(SourceUnavailableError):
        read_revision(make_source(tmp_path, type=SourceType.GIT))


def test_read_revision_declared_ref_that_does_not_resolve(tmp_path, make_git_repo,
                                                        make_source):
    """The registry and the repository disagree — do not silently pick another."""
    repo = make_git_repo()
    repo.write("a.md", "one")
    repo.commit()

    with pytest.raises(GitError):
        read_revision(make_source(repo.path, ref="does-not-exist"))


def test_resolve_git_revision_returns_none_without_commits(tmp_path, make_git_repo):
    repo = make_git_repo()
    assert resolve_git_revision(repo.path, "main") is None


def test_is_known_commit_distinguishes_a_digest_from_a_commit(tmp_path, make_git_repo):
    repo = make_git_repo()
    repo.write("a.md", "one")
    commit = repo.commit()

    assert is_known_commit(repo.path, commit)
    assert not is_known_commit(repo.path, "0" * 40)
    assert not is_known_commit(repo.path, f"{CONTENT_REVISION_PREFIX}abc")
    assert not is_known_commit(repo.path, "")


# ------------------------------------------------------------ change types ---

def test_changed_paths_classifies_added_modified_and_deleted(tmp_path, make_git_repo,
                                                             make_source):
    repo = make_git_repo()
    repo.write("modified.md", "original")
    repo.write("deleted.md", "goodbye")
    repo.commit("base")
    before = repo.head()

    repo.write("modified.md", "changed")
    repo.remove("deleted.md")
    repo.write("added.md", "new")
    repo.commit("second")

    changes = {c.path: c for c in changed_paths(make_source(repo.path), before, repo.head())}
    assert changes["added.md"].change_type is ChangeType.ADDED
    assert changes["modified.md"].change_type is ChangeType.MODIFIED
    assert changes["deleted.md"].change_type is ChangeType.DELETED


def test_changed_paths_detects_a_rename_and_its_similarity(tmp_path, make_git_repo,
                                                           make_source):
    repo = make_git_repo()
    repo.write("original.md", "# A document\n\n" + "Body text.\n" * 40)
    repo.commit("base")
    before = repo.head()

    repo.move("original.md", "renamed.md")
    repo.commit("rename")

    changes = changed_paths(make_source(repo.path), before, repo.head())
    assert len(changes) == 1
    change = changes[0]
    assert change.change_type is ChangeType.RENAMED
    assert change.path == "renamed.md"
    assert change.previous_path == "original.md"
    assert change.similarity == 100
    assert change.is_exact_rename


def test_changed_paths_reports_an_inexact_rename_as_such(tmp_path, make_git_repo,
                                                         make_source):
    repo = make_git_repo()
    repo.write("original.md", "line one\n" * 60)
    repo.commit("base")
    before = repo.head()

    repo.move("original.md", "renamed.md")
    repo.write("renamed.md", "line one\n" * 55 + "entirely different\n" * 5)
    repo.commit("rename and edit")

    change = changed_paths(make_source(repo.path), before, repo.head())[0]
    assert change.change_type is ChangeType.RENAMED
    assert change.similarity is not None
    assert not change.is_exact_rename


def test_changed_paths_is_empty_for_an_unchanged_range(tmp_path, make_git_repo,
                                                       make_source):
    repo = make_git_repo()
    repo.write("a.md", "one")
    commit = repo.commit()

    assert changed_paths(make_source(repo.path), commit, commit) == ()


def test_changed_paths_returns_none_when_the_previous_revision_is_unknown(
    tmp_path, make_git_repo, make_source
):
    """"Nothing changed" and "we cannot tell" must not be the same answer."""
    repo = make_git_repo()
    repo.write("a.md", "one")
    repo.commit()

    assert changed_paths(make_source(repo.path), "0" * 40, repo.head()) is None


def test_changed_paths_handles_filenames_with_spaces_and_quotes(
    tmp_path, make_git_repo, make_source
):
    """-z with quotepath=false, so a path is never C-escaped before lookup."""
    repo = make_git_repo()
    awkward = 'a file with spaces and "quotes".md'
    repo.write("plain.md", "one")
    repo.commit("base")
    before = repo.head()

    repo.write(awkward, "two")
    repo.commit("awkward")

    paths = [c.path for c in changed_paths(make_source(repo.path), before, repo.head())]
    assert awkward in paths
