# Assignment 6 · Split it, measure it, decide

Model: Mistral, ministral-14b-2512. All runs use this model.

## Part A · The gates, before you build

**The roles you considered, and what each would need from the others mid-task.**

| Two roles | What one needs from the other while the task runs | How it would get it | What that costs |
|---|---|---|---|
| Investigator → writer | The writer needs the finding: the label, the file, and one sentence about the change. The writer cannot start without the finding. | The coordinator sends it between rounds. The accepted return of the investigator becomes the brief of the writer. | The writer has no read tools. Thus, the writer loses all data that the return does not contain. Each issue also gets a second context (prompt, tool schemas, brief). |
| Writer → investigator | The writer needs nothing more. But a finding with too little data gives a weak pull request body. | The writer cannot ask during the task. The coordinator rejects a return that has no evidence. Then the coordinator asks the investigator again. | A weak pull request body, or one more round of investigator tokens. |
| Investigator → reviewer (examined, not used) | The reviewer needs the full record of the investigator: the files that it read, and the files that it rejected, with the reasons. | The full record goes into the context of the reviewer, or into a shared notes file. | Full records fill each context. The reviewer uses the same model, thus it has the same blind spots. Its agreement is weak evidence (slides 11, 41). |
| Patch author ↔ investigator (examined, not used) | The patch author needs the finding and the code of the file. It must read the same files again. | Messages during the task, or a second read of the same files. | The same reads occur two times. The daily task opens a draft pull request, not a patch. Thus, this role has no work. |
| Investigator-a ↔ investigator-b (batch) | Nothing. The five issues are not related. | No channel is necessary. | No cost. Two issues can name the same file. Each issue then gets its own branch and pull request. Nothing they share is written: investigators only read. |
| Writer-a ↔ writer-b (batch) | Nothing. Each writer writes only to its own issue. | No channel is necessary. | The tracker is shared, but each writer writes to a different issue. No write changes the data of a different writer. |
| Coordinator ↔ each worker | The coordinator needs the return of each worker. | Between rounds, as a return that the code checks. | One wait for each worker. The coordinator also loses all data that a return does not contain. |

- For one issue: The roles operate in a sequence. The writer needs the finding of the investigator one time, at the end. No two roles operate at the same time. Thus, the split is a pipeline, not a set of parallel parts.
  - The investigator returns the label, the file and the evidence. It also returns a status (found, candidate or out_of_budget). The code adds the searches, the reads and the number of calls from the tool calls of the investigator. The investigator also returns the items that it did not examine, and the items that it could not find. The investigator cannot say if its finding is correct, because no test exists for a triage finding. It also cannot say why it rejected the other files.
  - The writer returns the writes that it did. The writer cannot say if the finding is correct, because it does not see the code.
  - The coordinator reads the end state from the tracker. It can say if the end state is consistent. It cannot say if the end state is correct.
- For a batch of five: The batch has five lanes, one lane for each issue. Each lane has an investigator and then a writer. No arrow connects two lanes. The five investigators operate at the same time. Each writer starts when the coordinator accepts the return of its own investigator. The returns are the same as for one issue, and they have the same limits. The tracker is the only shared state, and each lane writes to a different issue.

**The sketch** (text, or an image in `reports/`):

```
ONE ISSUE                                    (no arrow between roles during the task)

 runner --task: issue n, budget B--> COORDINATOR (code, no model)
                                         | 1. brief: "triage #n"
                                         v
                                   INVESTIGATOR-n   issues_read, code_search,
                                         |          code_read_file, code_run_tests
                                         | 2. return contract, checked by code
                                         v    (rejected and asked again if not valid)
                                    COORDINATOR
                                         | 3. brief: the accepted finding
                                         v    (label, file, evidence)
                                     WRITER-n       issues_label, pulls_open,
                                         |          issues_comment (code adds the disclosure)
                                         v
                                      TRACKER <---- 4. coordinator reads the end state:
                                                       the combined check

A BATCH OF FIVE                (five lanes at the same time; no arrow between lanes)

                  +-> INVESTIGATOR-a -> return -> COORD -> WRITER-a -+
 runner -> COORD -+-> INVESTIGATOR-b -> return -> COORD -> WRITER-b -+-> TRACKER -> combined check
 (5 issues, 5B)   +-> ...   c, d, e   ...                ...         |   (all five issues)
                  +-> INVESTIGATOR-e -> return -> COORD -> WRITER-e -+
```

**The four gates** (slide 46), in order, stopping at the first no.

| Gate | One issue | Why | A batch of five | Why |
|---|---|---|---|---|
| 1. The parts work mostly without talking | pass | The writer needs the finding only one time, at the end. The coordinator sends it. No role talks to a different role during the task. But the parts are a sequence, not parallel parts. | pass | The five issues are not related. No investigator needs the finding of a different investigator. No writer writes to a different issue. Each arrow stays in the lane of one issue. |
| 2. Each part's result can be checked on its own | pass | The code can check the result of the writer in the tracker with fixed rules. The rules are: one comment, its label on the issue, and one pull request that names the file (none when the file is none). The code can check the form of the investigator return: its status, and a file that it really read (from the trace). The code cannot check if the finding is correct, because no test exists for a triage finding. | pass | The code can check the end state of each issue with the same rules. It does not need the answer key. A check of the full result is also necessary, because each part can pass while the parts disagree. |
| 3. A team buys what one agent cannot get more cheaply | fail | No parallelism: one issue is a strict sequence. No problem with context size: one issue needs approximately ten steps in one context. One agent can get the split by tool surface. The code gives it the read tools first, and the write tools after. | pass | Parallelism: five investigations operate at the same time. One agent does one step at a time, thus it cannot get this benefit. Context isolation is also a real benefit, because one context in arm S holds all five issues. But one agent can get this benefit at a lower cost with a new context for each issue (slide 12). Arm S-plus tests this. |
| 4. The result is worth the multiplier | not_reached | Gate 3 failed, thus this gate is not reached. | pass (provisional) | On paper, the multiplier is less than 1, far below the lecture's reported 15× for multi-agent systems. Five short contexts use fewer tokens than one context that holds all the earlier issues. Thus, the split saves time at no added token cost. Part C tests the multiplier and the pass rate. |

- The benefit you are trying to buy, and the condition it needs:
  - Batch, first benefit: parallelism, which saves time. This benefit needs parts that are fully independent. Five issues that are not related, separate branches, no two writes to the same issue, and a rate limit that lets five calls run at once satisfy this condition.
  - Batch, second benefit: specialisation by tool surface. The investigator cannot write, and the writer cannot search. This changes the errors that each role can make. This benefit needs roles with really different requirements. Reads and writes are different requirements. But one agent gets most of this benefit when the code changes its tools by phase.
  - Context isolation is also present. But one agent can get it at a lower cost.
  - One issue: the split gives no benefit that one agent cannot get at a lower cost. We measure the split on one issue to test this verdict.
- Your prediction, as committed in `reports/PREDICTIONS_06.md`, and its commit:
  - Single tasks: arm M uses approximately 1.3 times the tokens of arm S. The two arms pass approximately the same number of tasks (S approximately 12 of 18, M approximately 11 of 18). Arm S-plus passes at least as many tasks as arm M, approximately 12 of 18.
  - Batch tasks: arm M uses approximately 0.5 times the tokens of arm S. Arm M passes a few more (full tasks: S approximately 1 of 6, M approximately 2 of 6; issues: S approximately 18 of 30, M approximately 24 of 30). Arm S-plus passes as many tasks as arm M.
  - Decision that I expect: one agent for single issues. One agent for batches also, unless the split does better than arm S-plus at the same budget.
  - Commit `<hash>` at `<time>` (write these after the commit).

## Part B · The split

- The coordinator and the roles, and the tools each holds:
- Why they split by tool surface:
- The return contract, field by field, and which fields come from the worker's tool calls:
- Each worker's share of the budget, and what is held back:
- The five checks, where each is in your code:

## Part C · Measured

**The five constants** (slide 59): model, tools, budget, evaluator, task set.

**The results.**

| Arm | Kind | Passes / runs | Lowest and highest sweep | Tasks all three passed | Mean tokens | Mean wall-clock (s) |
|---|---|---|---|---|---|---|
| S | single | | | | | |
| S | batch | | | | | |
| M | single | | | | | |
| M | batch | | | | | |
| S-plus | single | | | | | |
| S-plus | batch | | | | | |

- Your multiplier (M over S), single and batch, beside the lecture's 15×:
- Whether S-plus's spend matched M's in fact, task by task:

**Slide 18's three questions**, for each kind of task.

| Question | One issue | A batch of five |
|---|---|---|
| Did the split spend more? | | |
| Does spending more raise the score? | | |
| Given the same budget, did one agent do as well? | | |

- What you would have claimed from arms S and M alone, and what you claim now:

**Every arm M run that failed.**

| Run | What each agent read, wrote and waited on | The first thing that went wrong | Anomaly | MAST category |
|---|---|---|---|---|
| | | | | |

## Part D · The decision

- One issue:
- A batch of five:
- The condition that would reopen it:
- The record: `decisions/0006-topology.md`

## AI assistance

Which tool, what it wrote, and what you checked:
