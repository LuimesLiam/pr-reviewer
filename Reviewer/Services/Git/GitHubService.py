import base64
import os
import ast
import asyncio
import networkx as nx

from github import Github
from dotenv import load_dotenv

from .AbstractGitService import AbstractGitService

load_dotenv()
TOKEN = os.getenv("GIT_TOKEN")


class GitHubService(AbstractGitService):
    def __init__(self):
        # PyGithub client is still sync under the hood
        self.client = Github(TOKEN)

    async def get_repo(self, repo_name: str):
        return await asyncio.to_thread(self.client.get_repo, repo_name)

    async def list_open_pull_requests(self, repo_name: str):
        repo = await self.get_repo(repo_name)
        # wrap iteration in a thread
        return await asyncio.to_thread(lambda: list(repo.get_pulls(state="open")))

    async def get_pull_request(self, repo_name: str, pr_number: int):
        repo = await self.get_repo(repo_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)

        files = await asyncio.to_thread(lambda: list(pr.get_files()))
        diffs = []
        for f in files:
            diffs.append({
                "filename": f.filename,
                "status": f.status,
                "patch": f.patch if hasattr(f, "patch") else None
            })

        return {
            "title": pr.title,
            "user": pr.user.login,
            "body": pr.body,
            "head_branch": pr.head.ref,
            "diffs": diffs
        }

    async def get_file(self, repo_name: str, file_path: str, branch: str = "main"):
        repo = await self.get_repo(repo_name)
        content = await asyncio.to_thread(repo.get_contents, file_path, ref=branch)
        return {
            "path": content.path,
            "decoded_content": content.decoded_content.decode("utf-8")
        }

    async def get_file_from_pull_request(self, repo_name: str, pr_number: int, file_path: str):
        repo = await self.get_repo(repo_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)
        branch = pr.head.ref
        return await self.get_file(repo_name, file_path, branch=branch)

    async def get_all_files_from_pull_request(self, repo_name: str, pr_number: int):
        repo = await self.get_repo(repo_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)
        head_sha = pr.head.sha

        # get all changed file paths in PR
        files = await asyncio.to_thread(lambda: list(pr.get_files()))
        file_paths = [f.filename for f in files]

        # fetch full tree (may be large; careful with very big repos)
        tree = await asyncio.to_thread(repo.get_git_tree, head_sha, True)
        tree = tree.tree

        path_to_blob_sha = {
            item.path: item.sha
            for item in tree
            if item.path in file_paths and item.type == "blob"
        }

        file_contents = {}
        for path, sha in path_to_blob_sha.items():
            blob = await asyncio.to_thread(repo.get_git_blob, sha)
            if blob.encoding == "base64":
                decoded = base64.b64decode(blob.content).decode(
                    "utf-8", errors="replace")
                file_contents[path] = decoded
            else:
                file_contents[path] = None

        return file_contents

    async def group_files_in_pull_request(self, repo_name: str, pr_number: int):
        # fetch diffs
        repo = await self.get_repo(repo_name)
        pr = await asyncio.to_thread(repo.get_pull, pr_number)
        files = await asyncio.to_thread(lambda: list(pr.get_files()))

        # build maps of full content and raw patch
        file_contents = await self.get_all_files_from_pull_request(repo_name, pr_number)
        path_to_patch = {f.filename: (f.patch if hasattr(
            f, "patch") else None) for f in files}

        # CPU-bound grouping
        groups = await asyncio.to_thread(self._group_related_files, file_contents)

        grouped_info = []
        for group in groups:
            group_entries = []
            for path in group:
                patch = path_to_patch.get(path) or ""
                old_lines = [l for l in patch.splitlines() if l.startswith(
                    '-') and not l.startswith('---')]
                new_lines = [l for l in patch.splitlines() if l.startswith(
                    '+') and not l.startswith('+++')]
                entry = {
                    "file_path": path,
                    "old_diff": "\n".join(old_lines) if old_lines else None,
                    "new_diff": "\n".join(new_lines) if new_lines else None,
                    "full_content": file_contents.get(path)
                }
                group_entries.append(entry)
            grouped_info.append(group_entries)

        return grouped_info

    @staticmethod
    def _group_related_files(file_contents: dict):
        # identical to your original logic
        def_to_file = {}
        usage_graph = nx.Graph()
        usage_graph.add_nodes_from(file_contents.keys())

        file_identifiers = {}
        for path, content in file_contents.items():
            ids = set()
            try:
                if path.endswith(".py"):
                    tree = ast.parse(content or "", filename=path)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                            ids.add(node.name)
                else:
                    ids |= {w for w in (content or "").split() if len(
                        w) > 3 and w.isidentifier()}
            except SyntaxError:
                ids |= {w for w in (content or "").split()
                        if len(w) > 3 and w.isidentifier()}

            file_identifiers[path] = ids
            for ident in ids:
                def_to_file.setdefault(ident, set()).add(path)

        for ident, files in def_to_file.items():
            for a in files:
                for b in files:
                    if a != b:
                        usage_graph.add_edge(a, b)

        return [list(c) for c in nx.connected_components(usage_graph)]


if __name__ == "__main__":
    async def main():
        service = GitHubService()
        pr_data = await service.get_pull_request("LuimesLiam/HomeApp", 2)
        for diff in pr_data["diffs"]:
            print(f"File: {diff['filename']}\n{diff['patch']}\n")

        print("== Grouping files in PR #2 ==")
        groups = await service.group_files_in_pull_request("LuimesLiam/HomeApp", 2)
        for idx, grp in enumerate(groups, 1):
            print(f"Group {idx}:")
            for entry in grp:
                print(f"  {entry['file_path']}")
