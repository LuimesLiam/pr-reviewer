from abc import ABC, abstractmethod


class AbstractGitService(ABC):
    @abstractmethod
    async def list_open_pull_requests(self, repo_name: str):
        pass

    @abstractmethod
    async def get_pull_request(self, repo_name: str, pr_number: int):
        pass

    @abstractmethod
    async def get_file(self, repo_name: str, file_path: str, branch: str = "main"):
        pass

    @abstractmethod
    async def get_file_from_pull_request(self, repo_name: str, pr_number: int, file_path: str):
        pass

    @abstractmethod
    async def group_files_in_pull_request(self, repo_name: str, pr_number: int):
        pass

    @abstractmethod
    async def get_all_files_from_pull_request(self, repo_name: str, pr_number: int):
        pass

    # --- Added helper abstractions ---
    @abstractmethod
    async def get_pr_changed_file_paths(self, repo_name: str, pr_number: int) -> list[str]:
        """Return list of file paths changed in the PR (from diff listing)."""
        pass

    @abstractmethod
    async def find_file_in_pr(self, repo_name: str, pr_number: int, target: str) -> list[str]:
        """Heuristically search for a requested file path within the PR.
        Should attempt exact match, suffix match, and substring match on changed files; may fall back to repo tree.
        Returns a list of candidate full paths (best match first)."""
        pass
