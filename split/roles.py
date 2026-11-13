"""The split's two roles, by tool surface.

A role's surface is what its loop is given: run_loop needs only .schemas and .call. A
surface offers its own tools and refuses every other name here, before the registry, so
the run's registry sees no protocol error from a role asking for a tool it does not hold.
Every call a surface lets through goes to the run's registry and its hook.

The investigator holds the read tools and one local tool, its return. The writer holds
the three writes, for its own issue only; its comments pass with_disclosure in code.
"""

from __future__ import annotations

import copy

from harness.roles import arg, role_of, tool_for
from split.guards import contract_errors, contract_schema
from tools import ToolResult
from ways.agent import Disclosing

INVESTIGATOR_ROLES = ("read_issue", "search", "read_file", "run_tests")
WRITER_ROLES = ("apply_label", "open_pr", "comment")
RETURN_TOOL = "submit_finding"
FROM_CALLS = ("searched", "calls_used")      # facts about the run, filled in by code, never by the model


def refused(text: str) -> ToolResult:
    return ToolResult(text, True, 0.0)


def return_tool() -> dict:
    """The investigator's return tool: the contract less the fields code fills in."""
    schema = copy.deepcopy(contract_schema())
    schema.pop("title", None)
    for name in FROM_CALLS:
        schema["properties"].pop(name)
    schema["required"] = [r for r in schema["required"] if r not in FROM_CALLS]
    return {"name": RETURN_TOOL, "strict": True, "input_schema": schema,
            "description": ("Return your finding to the coordinator, once, when you are done. The coordinator "
                            "acts only on what you return here. The code adds what you searched and how many "
                            "calls you made, from your own tool calls: do not list them. A return that breaks "
                            "this shape is rejected, and you are asked again.")}


class InvestigatorSurface:
    """Reads of its own issue and the code, and a return the coordinator checks against the
    contract before it acts. After `max_calls` reads, the return is the only tool offered:
    the stopping rule is in code, not in the prompt."""

    def __init__(self, registry, worker_id: str, coordinator, issue: int, *, max_calls: int, stopped=None):
        self.registry, self.worker_id, self.coordinator = registry, worker_id, coordinator
        self.allowed = {tool_for(r) for r in INVESTIGATOR_ROLES}
        self.issue, self.max_calls, self.stopped = issue, max_calls, stopped
        self.calls = 0
        self.searched: list[str] = []
        self.accepted: dict | None = None
        self.returns = 0

    @property
    def spent(self) -> bool:
        return self.calls >= self.max_calls

    @property
    def schemas(self) -> list[dict]:
        reads = [] if self.spent else [s for s in self.registry.schemas if s["name"] in self.allowed]
        return reads + [return_tool()]

    def _note(self, name: str, tool_input) -> None:
        """Count the call the way the trace records it: every call to a course tool, refused or not."""
        role = role_of(name)
        if not role:
            return
        self.calls += 1
        inp = tool_input if isinstance(tool_input, dict) else {}
        value = (inp.get(arg("search", "query")) if role == "search"
                 else inp.get(arg("read_file", "path")) if role == "read_file" else None)
        if value is not None and str(value) not in self.searched:
            self.searched.append(str(value))

    def call(self, name: str, tool_input, **kwargs) -> ToolResult:
        if name == RETURN_TOOL:
            return self._return(tool_input)
        spent = self.spent
        self._note(name, tool_input)
        if self.stopped is not None and self.stopped.is_set():
            return refused("The coordinator stopped this worker. Make no more calls.")
        if self.accepted is not None:
            return refused("Your finding was accepted. Make no more calls: reply with the word done.")
        if spent:
            return refused(f"Your {self.max_calls} calls are spent. Call {RETURN_TOOL} now with your best answer, "
                           "status candidate or out_of_budget, and what you did not search in not_searched.")
        if name not in self.allowed:
            return refused(f"{name} is not one of your tools. You may call only {sorted(self.allowed)} "
                           f"and {RETURN_TOOL}.")
        if role_of(name) == "read_issue":
            named = str((tool_input or {}).get(arg("read_issue", "number"), "")).strip().lower() \
                if isinstance(tool_input, dict) else ""
            if named != f"issue-{self.issue}":
                return refused(f"You investigate only issue-{self.issue}, not {named or 'no issue'}.")
        result = self.registry.call(name, tool_input, **kwargs)
        if self.spent and not result.is_error:
            result.content += (f"\n\n[That was your last call. Call {RETURN_TOOL} now with your best answer.]")
        return result

    def _return(self, tool_input) -> ToolResult:
        if self.accepted is not None:
            return refused("Your finding was already accepted. Reply with the word done.")
        self.returns += 1
        contract = dict(tool_input) if isinstance(tool_input, dict) else tool_input
        if isinstance(contract, dict):
            contract["searched"] = list(self.searched)
            contract["calls_used"] = self.calls
        errors = contract_errors(contract)
        self.coordinator.trace.event("worker_return", worker=self.worker_id, contract=contract,
                                     valid=not errors, errors=errors)
        if errors:
            return refused("Rejected: your return breaks the contract. Fix these and call "
                           f"{RETURN_TOOL} again:\n- " + "\n- ".join(errors))
        self.accepted = contract
        return ToolResult("Accepted. Make no more calls: reply with the word done.", False, 0.0)


class WriterSurface:
    """The three writes, for one issue, against the finding version the writer was briefed with."""

    def __init__(self, registry, disclosure: str, issue: int, board, path: str, version: int):
        self.tools = Disclosing(registry, disclosure)
        self.allowed = {tool_for(r) for r in WRITER_ROLES}
        self.issue, self.board, self.path, self.version = issue, board, path, version

    @property
    def schemas(self) -> list[dict]:
        return [s for s in self.tools.schemas if s["name"] in self.allowed]

    def call(self, name: str, tool_input, **kwargs) -> ToolResult:
        if name not in self.allowed:
            return refused(f"{name} is not one of your tools. You may call only {sorted(self.allowed)}.")
        role = role_of(name)
        named = str((tool_input or {}).get(arg(role, "number"), "")).strip().lower() \
            if isinstance(tool_input, dict) else ""
        if named != f"issue-{self.issue}":
            return refused(f"You write only to issue-{self.issue}, not {named or 'no issue'}.")
        if self.board.version(self.path) != self.version:
            return refused("The finding changed after you were briefed. Make no more calls.")
        return self.tools.call(name, tool_input, **kwargs)
