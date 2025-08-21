from .AbstractGitService import AbstractGitService
from .GitHubService import GitHubService


def git_service_factory(provider: str) -> AbstractGitService:
    if provider == "github":
        return GitHubService()
    elif provider == "azure":
        raise NotImplementedError("Azure DevOps support not implemented yet.")
    else:
        raise ValueError(f"Unsupported git provider: {provider}")
