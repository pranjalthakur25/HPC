"""Unit tests for ``GitPythonMetadataCollector`` against real temporary git repos."""

from __future__ import annotations

from pathlib import Path

import git
import pytest

from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.infrastructure.collectors.git_collector import GitPythonMetadataCollector


@pytest.fixture
def repo(tmp_path: Path) -> git.Repo:
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    (tmp_path / "README.md").write_text("hello\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    return repo


def test_collect_returns_commit_and_branch_metadata(tmp_path: Path, repo: git.Repo) -> None:
    collector = GitPythonMetadataCollector()

    metadata = collector.collect(tmp_path)

    assert metadata.commit.sha == repo.head.commit.hexsha
    assert metadata.commit.message == "Initial commit"
    assert metadata.commit.author_name == "Test User"
    assert metadata.commit.author_email == "test@example.com"
    assert metadata.branch == repo.active_branch.name
    assert metadata.root_path.resolve() == tmp_path.resolve()
    assert metadata.is_dirty is False
    assert metadata.tags == ()
    assert metadata.remote_url is None


def test_collect_reports_dirty_working_tree(tmp_path: Path, repo: git.Repo) -> None:
    (tmp_path / "untracked.txt").write_text("scratch\n")
    collector = GitPythonMetadataCollector()

    metadata = collector.collect(tmp_path)

    assert metadata.is_dirty is True


def test_collect_includes_remote_url(tmp_path: Path, repo: git.Repo) -> None:
    repo.create_remote("origin", "https://example.org/repo.git")
    collector = GitPythonMetadataCollector()

    metadata = collector.collect(tmp_path)

    assert metadata.remote_url == "https://example.org/repo.git"


def test_collect_includes_tags_at_head(tmp_path: Path, repo: git.Repo) -> None:
    repo.create_tag("v1.0.0")
    collector = GitPythonMetadataCollector()

    metadata = collector.collect(tmp_path)

    assert metadata.tags == ("v1.0.0",)


def test_collect_returns_none_branch_for_detached_head(tmp_path: Path, repo: git.Repo) -> None:
    repo.git.checkout(repo.head.commit.hexsha)
    collector = GitPythonMetadataCollector()

    metadata = collector.collect(tmp_path)

    assert metadata.branch is None


def test_collect_raises_for_repo_without_commits(tmp_path: Path) -> None:
    git.Repo.init(tmp_path)
    collector = GitPythonMetadataCollector()

    with pytest.raises(MetadataCollectionError):
        collector.collect(tmp_path)


def test_collect_raises_for_non_git_directory(tmp_path: Path) -> None:
    collector = GitPythonMetadataCollector()
    # The drive root is never itself inside a git working tree, regardless of
    # where the rest of the filesystem (including tmp_path) happens to sit.
    drive_root = Path(tmp_path.anchor)

    with pytest.raises(MetadataCollectionError):
        collector.collect(drive_root)
