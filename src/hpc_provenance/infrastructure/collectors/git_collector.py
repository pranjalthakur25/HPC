"""GitPython-backed implementation of ``GitMetadataCollector``."""

from __future__ import annotations

from pathlib import Path

import git

from hpc_provenance.domain.exceptions import MetadataCollectionError
from hpc_provenance.domain.interfaces.collectors import GitMetadataCollector
from hpc_provenance.domain.models.git_metadata import GitCommit, GitRepositoryMetadata


class GitPythonMetadataCollector(GitMetadataCollector):
    """Reads repository, branch, commit, dirty-state, and tag information
    using ``GitPython``.
    """

    def collect(self, repository_path: Path) -> GitRepositoryMetadata:
        """See ``GitMetadataCollector.collect``."""
        try:
            repo = git.Repo(repository_path, search_parent_directories=True)
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as exc:
            raise MetadataCollectionError(
                f"{repository_path} is not inside a git working tree"
            ) from exc

        try:
            head_commit = repo.head.commit
        except ValueError as exc:
            raise MetadataCollectionError(
                f"git repository at {repository_path} has no commits"
            ) from exc

        commit = GitCommit(
            sha=head_commit.hexsha,
            author_name=head_commit.author.name or "",
            author_email=head_commit.author.email or "",
            committed_at=head_commit.committed_datetime,
            message=head_commit.message.strip(),
        )

        try:
            branch: str | None = repo.active_branch.name
        except TypeError:
            # Detached HEAD: there is no active branch.
            branch = None

        tags = tuple(tag.name for tag in repo.tags if tag.commit == head_commit)

        remote_url: str | None = None
        if repo.remotes:
            try:
                remote_url = repo.remote("origin").url
            except ValueError:
                remote_url = repo.remotes[0].url

        try:
            is_dirty = repo.is_dirty(untracked_files=True)
        except Exception as exc:
            raise MetadataCollectionError(
                f"failed to determine dirty state for {repository_path}"
            ) from exc

        return GitRepositoryMetadata(
            remote_url=remote_url,
            branch=branch,
            tags=tags,
            is_dirty=is_dirty,
            root_path=Path(repo.working_tree_dir),
            commit=commit,
        )
        
        
if __name__ == "__main__":

    repository_path = Path(r"C:\Users\DELL\Downloads\HPC_AI_BOMs")
    collector = GitPythonMetadataCollector()
    metadata = collector.collect(repository_path)
    print(metadata)
