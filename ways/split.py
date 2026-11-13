"""Arm M, the split: a coordinator in code, and two roles split by tool surface.

For each of the task's issues, a lane: an investigator (the read tools and a return) and
then a writer (the label, the draft pull request and the comment, for that issue only).
The coordinator acts only on a return that fits split/contract.schema.json, and briefs
the writer from it. In a batch the five lanes run at once; nothing crosses between lanes.

Budget: each issue's share is the run's budget over its issues. Of that share, the
investigator gets 60%, the writer 25%, and 15% is held back for a second investigator
when the first returns nothing valid. Every agent's calls count against the run's one
ceiling (ctx.agent's clients).

The five checks: the contract (split/roles.py, InvestigatorSurface._return), the wait
graph (split/guards.py, WaitGraph, fed by every wait below), compare-and-set on the
findings board the lanes share with their writers (SharedState), the combined check of
the end state read from the tracker after the last write (check_combined), and one
trace: every line here is written through an agent's trace.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

from agent.loop import Bounds, load_bounds, run_loop
from harness.tasks import end_state
from split.guards import COORDINATOR, SharedState, WaitGraph, check_combined
from split.roles import InvestigatorSurface, WriterSurface
from ways.agent import disclosure_line

INVESTIGATOR_SHARE, WRITER_SHARE, HELD_BACK = 0.60, 0.25, 0.15
INVESTIGATOR_CALLS = 8                          # reads before the return is the only tool offered
INVESTIGATOR_STEPS, WRITER_STEPS = 11, 6       # eight reads, a return, one re-ask, one to say done; three writes and room


class Coordinator:
    def __init__(self, ctx):
        self.ctx = ctx
        self.agent = ctx.agent(COORDINATOR)
        self.graph = WaitGraph()
        self.board = SharedState({self.path(n): "" for n in ctx.issues})
        self.stops: dict[str, threading.Event] = {}
        bounds = load_bounds()
        self.wall = bounds.wall_clock_s
        self.per_issue = (ctx.budget // len(ctx.issues)) if ctx.budget else bounds.max_tokens

    @staticmethod
    def path(issue: int) -> str:
        return f"finding/{issue}"

    def wait(self, on: str, what: str, turn: int) -> None:
        """The coordinator waits on a worker: traced, and given to the wait graph."""
        self.agent.trace.event("wait", waiter=COORDINATOR, on=on, what=what, turn=turn)
        cycle = self.graph.wait(COORDINATOR, on, what)
        if cycle:
            victim = self.graph.victim(cycle)
            self.stops.setdefault(victim, threading.Event()).set()
            self.agent.trace.event("worker_stopped", worker=victim, reason=f"a cycle of waits: {' -> '.join(cycle)}")

    def investigate(self, issue: int) -> dict | None:
        """The accepted return for this issue, or None if no investigator returned a valid one."""
        attempts = [(f"investigator-{issue}", INVESTIGATOR_SHARE), (f"investigator-{issue}-2", HELD_BACK)]
        for turn, (worker_id, share) in enumerate(attempts):
            worker = self.ctx.agent(worker_id, parent=COORDINATOR)
            stop = self.stops.setdefault(worker_id, threading.Event())
            surface = InvestigatorSurface(self.ctx.tools, worker_id, self.agent, issue,
                                          max_calls=INVESTIGATOR_CALLS, stopped=stop)
            self.wait(worker_id, "a finding", turn)
            run_loop(worker.client, surface, self.ctx.prompt("investigator.md"), f"Investigate issue #{issue}.",
                     Bounds(INVESTIGATOR_STEPS, int(self.per_issue * share), self.wall), worker.trace)
            self.graph.release(COORDINATOR, worker_id)
            if surface.accepted is not None:
                return surface.accepted
        return None

    def write(self, issue: int, finding: dict) -> None:
        path = self.path(issue)
        _, seen = self.board.read(COORDINATOR, path)
        self.board.write(COORDINATOR, path, json.dumps(finding["result"], sort_keys=True), seen)
        writer_id = f"writer-{issue}"
        writer = self.ctx.agent(writer_id, parent=COORDINATOR)
        content, version = self.board.read(writer_id, path)
        result = json.loads(content)
        brief = (f"Write the triage of issue #{issue} from this finding.\n"
                 f"label: {result['label']}\nfile: {result['file']}\nevidence: {result['evidence']}")
        surface = WriterSurface(self.ctx.tools, disclosure_line(), issue, self.board, path, version)
        self.wait(writer_id, "the writes", 2)
        run_loop(writer.client, surface, self.ctx.prompt("writer.md"), brief,
                 Bounds(WRITER_STEPS, int(self.per_issue * WRITER_SHARE), self.wall), writer.trace)
        self.graph.release(COORDINATOR, writer_id)

    def lane(self, issue: int) -> None:
        finding = self.investigate(issue)
        if finding is not None:
            self.write(issue, finding)

    def run(self) -> None:
        issues = self.ctx.issues
        with ThreadPoolExecutor(max_workers=len(issues)) as pool:
            list(pool.map(self.lane, issues))
        state = end_state(self.ctx.tracker, self.ctx.run_id, self.ctx.task)
        violations = check_combined(self.ctx.task, state)
        self.agent.trace.event("combined_check", passed=not violations, violations=violations)


def run(ctx) -> None:
    Coordinator(ctx).run()
