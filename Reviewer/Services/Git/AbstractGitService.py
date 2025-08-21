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
