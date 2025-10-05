import asyncio
import json
import os
import logging

logger = logging.getLogger(__name__)


async def load_instructions(self) -> str:
    logger.debug("Loading instructions")
    instructions_dir = os.path.join(
        os.path.dirname(__file__), "Instructions")
    parts = []
    for fname in ["general.txt", "PythonSet.txt", "dotnetSet.txt"]:
        path = os.path.join(instructions_dir, fname)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    content = f.read().strip()
                    parts.append(content)
                    logger.debug(
                        "Loaded instruction file %s (%d chars)", fname, len(content))
            except Exception as e:
                logger.warning(
                    "Failed reading instruction file %s: %s", fname, e)
        else:
            logger.debug("Instruction file missing: %s", fname)
    result = "\n\n".join(parts)
    logger.debug("Aggregated instructions length=%d", len(result))
    return result


async def fetch_diffs(self, state: State) -> Command:
    logger.debug("fetch_diffs called with state keys=%s",
                 list(state.keys()))
    q = state.get("event_queue")
    repo = state.get("repo_name")
    pr = state.get("pr_number")
    logger.info("Fetching diffs for repo=%s pr=%s", repo, pr)
    if q:
        await q.put(f"▶️ Fetching diffs for {repo} PR #{pr}")
    pr_data = await self.git_service.get_pull_request(repo, pr)
    logger.debug("PR data type=%s keys=%s", type(pr_data).__name__, list(
        pr_data.keys()) if isinstance(pr_data, dict) else 'n/a')
    diffs = pr_data.get("diffs", []) if isinstance(pr_data, dict) else []
    logger.info("Fetched %d diffs", len(diffs))
    if q:
        await q.put(f"📂 {len(diffs)} diffs fetched")
    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=f"Loaded {len(diffs)} diffs"))
    return Command(update={
        "diffs": diffs,
        "current_diff_index": 0,
        "additional_context": {},
        "pending_context_request": [],
        "context_round": 0,
        "messages": messages
    }, goto="review_single_diff")


async def _build_context_section(self, additional_context: Dict[str, str]) -> str:
    logger.debug("Building context section for %d files",
                 len(additional_context))
    if not additional_context:
        return "(none)"
    sections = []
    for path, content in additional_context.items():
        snippet = content[:1500]  # truncate to control prompt size
        logger.debug("Context file included path=%s size=%d truncated_to=%d", path, len(
            content), len(snippet))
        sections.append(f"--- {path} ---\n{snippet}")
    joined = "\n\n".join(sections)
    logger.debug("Context section total length=%d", len(joined))
    return joined
