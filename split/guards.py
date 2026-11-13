"""The split's guards (checks/FORMATS.md, section 14.6), and the contract check.

The checker's replays call WaitGraph, SharedState and check_combined, and nothing else here.
None of them coordinates anything: each records or checks what happened.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path, PurePosixPath

from harness.formats import LABELS, normalize_path, parse_triage_comment
from harness.schema import errors as schema_errors

CONTRACT_PATH = Path(__file__).resolve().parent / "contract.schema.json"
COORDINATOR = "coordinator"


# -- 1. the return contract ------------------------------------------------------------------

def contract_schema() -> dict:
    return json.loads(CONTRACT_PATH.read_text())


def contract_errors(contract, schema: dict | None = None) -> list[str]:
    """A return's breaks of split/contract.schema.json; [] when it fits. Never repaired."""
    return schema_errors(contract, schema or contract_schema())


# -- 2. deadlock: who waits on whom ----------------------------------------------------------

class WaitGraph:
    """Every live wait, as an edge waiter -> on. A wait that closes a cycle is a deadlock."""

    def __init__(self):
        self._edges: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def wait(self, waiter: str, on: str, what: str = "") -> list[str] | None:
        """Record that `waiter` now waits on `on`. The cycle this wait closes, as the
        agents in it, or None."""
        with self._lock:
            self._edges.setdefault(str(waiter), set()).add(str(on))
            path = self._path(str(on), str(waiter))
            return path if path else None

    def release(self, waiter: str, on: str) -> None:
        """`waiter` has what it waited for: its edge goes."""
        with self._lock:
            self._edges.get(str(waiter), set()).discard(str(on))

    def victim(self, cycle: list[str]) -> str:
        """The worker to stop to break the cycle: the first agent in it that is not the
        coordinator. wait() puts the agent whose wait closed the cycle first."""
        workers = [a for a in cycle if a != COORDINATOR]
        if not workers:
            raise ValueError("a cycle of the coordinator alone has no worker to stop")
        return workers[0]

    def _path(self, start: str, goal: str) -> list[str] | None:
        """Agents from `goal` through `start` and back to `goal`, if `start` reaches `goal`."""
        stack, seen = [(start, [goal, start])], {start}
        while stack:
            node, path = stack.pop()
            if node == goal:
                return path[:-1]
            for nxt in sorted(self._edges.get(node, ())):
                if nxt == goal:
                    return path
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
        return None


# -- 3. compare-and-set on shared state ------------------------------------------------------

class SharedState:
    """Shared paths with a version each. A write names the version its agent read, and is
    refused if the path has changed since: a stale write never erases a newer one."""

    def __init__(self, initial: dict[str, str]):
        self._content = {str(k): str(v) for k, v in (initial or {}).items()}
        self._version = {k: 0 for k in self._content}
        self._lock = threading.Lock()
        self.refused: list[dict] = []

    def read(self, agent: str, path: str) -> tuple[str, int]:
        """The content and its version."""
        with self._lock:
            return self._content.get(path, ""), self._version.get(path, 0)

    def version(self, path: str) -> int:
        with self._lock:
            return self._version.get(path, 0)

    def write(self, agent: str, path: str, content: str, version: int) -> bool:
        """Compare-and-set: write only if `path` is still at `version`, the version the
        agent read. True when written; False when refused, leaving the content as it was."""
        with self._lock:
            now = self._version.get(path, 0)
            if version != now:
                self.refused.append({"agent": agent, "path": path, "read": version, "now": now})
                return False
            self._content[path] = str(content)
            self._version[path] = now + 1
            return True

    def content(self, path: str) -> str:
        with self._lock:
            return self._content.get(path, "")


# -- 4. the combined result ------------------------------------------------------------------

def _names(text: str, file: str) -> bool:
    text = (text or "").lower()
    return file.lower() in text or PurePosixPath(file).name.lower() in text


def check_combined(task, state: dict) -> list[str]:
    """The combined result's violations of the task's rules; [] when it passes.

    The rules are set before the run and need no answer key. For each issue: one comment,
    with label and file lines; exactly that label on the issue; one pull request naming
    the comment's file when the file is not none, and none when it is."""
    violations = []
    for issue in task.issues:
        part = state.get(int(issue)) or state.get(str(issue)) or {}
        comments, labels, prs = part.get("comments") or [], part.get("labels") or [], part.get("prs") or []
        if len(comments) != 1:
            violations.append(f"#{issue}: {len(comments)} comments, not one")
            continue
        label, file = parse_triage_comment(comments[0])
        if label not in LABELS or file is None:
            violations.append(f"#{issue}: the comment lacks a label line or a file line ({label!r}, {file!r})")
            continue
        file = normalize_path(file)
        applied = sorted({str(x).strip().lower() for x in labels})
        if applied != [label]:
            violations.append(f"#{issue}: labels on the issue {applied}, where the comment says {label!r}")
        if file == "none":
            if prs:
                violations.append(f"#{issue}: {len(prs)} pull requests, where the comment's file is none")
        elif len(prs) != 1:
            violations.append(f"#{issue}: {len(prs)} pull requests, not one, for {file}")
        elif not _names(f"{prs[0].get('title', '')}\n{prs[0].get('body', '')}", file):
            violations.append(f"#{issue}: the pull request does not name {file}, the comment's file")
    return violations


__all__ = ["WaitGraph", "SharedState", "check_combined", "contract_schema", "contract_errors"]
