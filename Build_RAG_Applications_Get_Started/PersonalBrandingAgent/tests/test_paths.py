"""Tests for app.paths: absolute, canonical, CWD-independent."""
import os
import subprocess
import sys

from app import paths


def test_all_paths_absolute():
    for path in (paths.PROJECT_ROOT, paths.DATA_DIR, paths.CHROMA_DIR):
        assert path.is_absolute()


def test_data_dir_exists_and_is_the_real_kb():
    assert paths.DATA_DIR.is_dir()
    # A known category from the real corpus.
    assert (paths.DATA_DIR / "evidence").is_dir()


def test_chroma_dir_defaults_inside_project():
    assert paths.CHROMA_DIR.parent == paths.PROJECT_ROOT
    assert paths.CHROMA_DIR.name == "chroma_db"


def test_paths_independent_of_cwd(tmp_path):
    """Importing app.paths from a different CWD must resolve identically."""
    code = (
        "import sys, json; sys.path.insert(0, %r); "
        "from app import paths; "
        "print(json.dumps(str(paths.DATA_DIR)))" % str(paths.PROJECT_ROOT)
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(paths.PROJECT_ROOT)},
        check=True,
    )
    assert result.stdout.strip().strip('"') == str(paths.DATA_DIR)


def test_ensure_runtime_dirs_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "logs")
    paths.ensure_runtime_dirs()
    assert (tmp_path / "chroma").is_dir()
    assert (tmp_path / "logs").is_dir()
    paths.ensure_runtime_dirs()  # second call must not raise
