"""Arm S-plus: one agent given what arm M actually spent (run.py --match split).

Slide 16's fair rival. For each issue in turn, the agent makes attempts with read-only
tools, each in a fresh context, until it has spent about its share of the budget. Then it
chooses an answer by a vote over its attempts (the answer most attempts gave; on a tie, the
earliest), computed without the known answers, and writes only that answer, once, in code:
the label, a draft pull request when the file is not none, and the comment last, which
passes with_disclosure before the registry.

Nothing runs at once and there are no roles: one agent, one attempt at a time. Each issue's
share is what is left of the run's budget over the issues left, so an issue that spends
less leaves more for the next. Each attempt is its own agent of the run
(attempt-<k>-<issue>), with its own client and trace, because Assignment 1's loop ends the
trace it is given.
"""

from __future__ import annotations

from collections import Counter

from agent.loop import Bounds, load_bounds, run_loop
from harness.formats import LABELS, format_triage_comment, normalize_path
from harness.roles import arg, role_of, tool_for
from tools import ToolResult
from ways.agent import Disclosing, disclosure_line

ANSWER_TOOL = "submit_answer"
READ_ROLES = ("read_issue", "search", "read_file", "run_tests")
MAX_CALLS, MAX_STEPS = 8, 11      # as the split's investigator: eight reads, an answer, room to retry, done
MIN_LEFT = 3000                   # fewer tokens than this left for an issue: no new attempt
MAX_ATTEMPTS = 25

ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["label", "file", "evidence"],
    "properties": {
        "label": {"type": "string", "enum": list(LABELS)},
        "file": {"type": "string", "description": "The file most responsible, relative to the repository root, or none."},
        "evidence": {"type": "string", "description": "One or two sentences: what in that file explains the issue, and what to change."},
    },
}


class AttemptSurface:
    """One attempt's tools: the reads, for its own issue, and an answer tool."""

    def __init__(self, registry, issue: int):
        self.registry, self.issue = registry, issue
        self.allowed = {tool_for(r) for r in READ_ROLES}
        self.calls = 0
        self.answer: dict | None = None

    @property
    def schemas(self) -> list[dict]:
        reads = [] if self.calls >= MAX_CALLS else [s for s in self.registry.schemas if s["name"] in self.allowed]
        return reads + [{"name": ANSWER_TOOL, "strict": True, "input_schema": ANSWER_SCHEMA,
                         "description": "Give your answer for the issue, once, when you are done."}]

    def call(self, name: str, tool_input, **kwargs) -> ToolResult:
        if name == ANSWER_TOOL:
            if self.answer is not None:
                return ToolResult("You already answered. Reply with the word done.", True, 0.0)
            if not isinstance(tool_input, dict) or tool_input.get("label") not in LABELS \
                    or not isinstance(tool_input.get("file"), str) or not tool_input.get("file").strip():
                return ToolResult("Rejected: give label (bug, feature, question or docs), file and evidence.", True, 0.0)
            self.answer = {"label": tool_input["label"], "file": normalize_path(tool_input["file"]),
                           "evidence": str(tool_input.get("evidence") or "")}
            return ToolResult("Recorded. Make no more calls: reply with the word done.", False, 0.0)
        spent = self.calls >= MAX_CALLS
        if role_of(name):
            self.calls += 1
        if self.answer is not None:
            return ToolResult("You already answered. Reply with the word done.", True, 0.0)
        if spent:
            return ToolResult(f"Your {MAX_CALLS} calls are spent. Call {ANSWER_TOOL} now with your best answer.", True, 0.0)
        if name not in self.allowed:
            return ToolResult(f"{name} is not one of your tools. You may call only {sorted(self.allowed)} "
                              f"and {ANSWER_TOOL}.", True, 0.0)
        if role_of(name) == "read_issue":
            named = str(tool_input.get(arg("read_issue", "number"), "")).strip().lower() if isinstance(tool_input, dict) else ""
            if named != f"issue-{self.issue}":
                return ToolResult(f"You triage only issue-{self.issue}, not {named or 'no issue'}.", True, 0.0)
        return self.registry.call(name, tool_input, **kwargs)


def vote(answers: list[dict]) -> dict | None:
    """The (label, file) most attempts gave; on a tie, the one given first. None without answers."""
    if not answers:
        return None
    counts = Counter((a["label"], a["file"]) for a in answers)
    best = max(counts.values())
    winner = next((a["label"], a["file"]) for a in answers if counts[(a["label"], a["file"])] == best)
    return next(a for a in answers if (a["label"], a["file"]) == winner)


def write(lead, issue: int, chosen: dict) -> None:
    """The chosen answer, written once: label, pull request when the file is not none, comment last."""
    number = f"issue-{issue}"
    label, file, evidence = chosen["label"], chosen["file"], chosen["evidence"].strip()
    step = 0
    lead.call_tool(step, tool_for("apply_label"), {arg("apply_label", "number"): number,
                                                    arg("apply_label", "label"): label})
    if file != "none":
        lead.call_tool(step, tool_for("open_pr"), {
            arg("open_pr", "number"): number, arg("open_pr", "branch"): f"repomind/issue-{issue}",
            arg("open_pr", "title"): f"Fix issue {issue} in {file}"[:120],
            arg("open_pr", "body"): f"File: {file}\n\n{evidence or 'Change the code there.'}"[:4000]})
    lead.call_tool(step, tool_for("comment"), {arg("comment", "number"): number,
                                               arg("comment", "body"): format_triage_comment(label, file, evidence)[:2000]})


def run(ctx) -> None:
    issues = ctx.issues
    bounds = load_bounds()
    budget = ctx.budget or bounds.max_tokens * len(issues)
    lead = ctx.agent("splus")
    lead.tools = Disclosing(ctx.tools, disclosure_line())       # every comment passes with_disclosure
    prompt = ctx.prompt("attempt.md")
    for i, issue in enumerate(issues):
        share = (budget - ctx.client.total_tokens) // (len(issues) - i)
        start = ctx.client.total_tokens
        answers = []
        for k in range(1, MAX_ATTEMPTS + 1):
            left = share - (ctx.client.total_tokens - start)
            if left < MIN_LEFT:
                break
            attempt = ctx.agent(f"attempt-{k}-{issue}", parent="splus")
            surface = AttemptSurface(ctx.tools, issue)
            run_loop(attempt.client, surface, prompt, f"Triage issue #{issue}.",
                     Bounds(MAX_STEPS, left, bounds.wall_clock_s), attempt.trace)
            if surface.answer is not None:
                answers.append(surface.answer)
        chosen = vote(answers)
        lead.trace.event("vote", issue=issue, attempts=len(answers),
                         answers=[[a["label"], a["file"]] for a in answers],
                         chosen=[chosen["label"], chosen["file"]] if chosen else None)
        if chosen is not None:
            write(lead, issue, chosen)
