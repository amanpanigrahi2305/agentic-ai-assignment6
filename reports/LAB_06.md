# Assignment 6 · Split it, measure it, decide

**Model:** OpenAI `gpt-4.1-mini` (served as `gpt-4.1-mini-2025-04-14`). All 72 measured runs used this model.

**Model change after the prediction:** The prediction, committed as `946e454`, specifies Mistral `ministral-14b-2512`. However, before starting any measured runs, a test showed that the Mistral API key was limited to 2 requests per minute. At that rate, processing a single issue would exceed the 180-second wall-clock limit specified in `agent/bounds.yaml`, and completing all 72 runs would take approximately 17 hours. Therefore, I switched to `gpt-4.1-mini` before the first measured run. None of the measured runs used Mistral, and the committed prediction file was left unchanged.

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
  - Commit `946e454` at 2026-11-12T20:50:56-06:00, on `main`, before any run of the split.

## Part B · The split

- The coordinator and the roles, and the tools each holds:
  - **Coordinator** (`ways/split.py`): The coordinator is implemented in code, not as a model. It has no tools and does not make any model calls. It starts the workers, checks their return values, briefs the writer, and runs the combined check.
  - **Investigator** (one per issue; `split/roles.py`, `InvestigatorSurface`): Each investigator can use `issues_read` to read only its own issue, along with `code_search`, `code_read_file`, and `code_run_tests`. It also has access to a local tool, `submit_finding`, which it uses to return its findings.
  - **Writer** (one per issue; `split/roles.py`, `WriterSurface`): Each writer can use `issues_label`, `pulls_open`, and `issues_comment`, but only for its own issue. Before a comment reaches the registry, the code passes it through `with_disclosure`.
  - **Batch execution:** All five lanes run at the same time. Each lane first runs an investigator and then a writer.
- Why they split by tool surface:
  - The two roles have different responsibilities: one is responsible only for reading, while the other is responsible only for writing.
  - Each role has a separate surface that limits the types of mistakes it can make. The investigator cannot write anything before submitting a finding, and the writer cannot search for information or change the finding.
  - Each surface rejects any tool name that is not allowed for that role before the call reaches the registry. This means an incorrect tool name does not cause a protocol error in the shared registry. All accepted calls still go through the registry and the policy hook.
- The return contract, field by field, and which fields come from the worker's tool calls (`split/contract.schema.json`):
  - `result`: Contains the label (one of four options), the file (or none), and the supporting evidence. The model provides this field.
  - `status`: Indicates whether the result is `found`, `candidate`, or `out_of_budget`. The model provides this field.
  - `searched`: Lists each query and path the worker submitted, once each. The code collects this information from the worker's tool calls.
  - `not_searched`: Lists the leads the worker did not follow. The model provides this field.
  - `calls_used`: Records the number of calls the worker made to the course tools before returning. The code calculates this from the worker's tool calls.
  - `could_not_determine`: Describes what the worker could not establish. The model provides this field.
  - The model never sees the two code-generated fields in its return tool. The code adds those fields and then validates the complete return against the schema. If the return does not match the schema, it is rejected and recorded with `valid: false`. The worker receives the validation errors and gets another chance to submit its return. The code does not attempt to repair an invalid return.
- Each worker's share of the budget, and what is held back:
  - The run budget is divided equally among the issues, so each issue gets 250,000 tokens (`B = 250,000`).
  - The investigator gets 60% of the issue budget and a limit of 8 calls. After 8 calls, `submit_finding` is the only tool it is offered. The code enforces this stopping rule; the prompt does not.
  - The writer gets 25% of the issue budget and a limit of 6 steps.
  - The remaining 15% is held back for a second investigator. The coordinator starts it only if the first investigator does not return a valid result. This did not happen in any of the 24 measured runs.
  - All agents share one run ceiling, because each gets its client from `ctx.agent`.
- The five checks, where each is in your code:
  1. **Return contract:** Implemented in `split/roles.py` through `InvestigatorSurface._return`, with validation handled by `contract_errors` in `split/guards.py`. It checks each return and records it as a `worker_return` line.
  2. **Deadlock detection:** Implemented in `split/guards.py` through `WaitGraph`. In `ways/split.py`, each wait is recorded as a `wait` line and passed to the graph. If the graph detects a cycle, it stops one worker and records a `worker_stopped` line.
  3. **Combined check:** Implemented in `split/guards.py` through `check_combined`. It runs after the final write and checks the tracker's final state, rather than relying on the workers' reports.
  4. **Idempotency and compare-and-set:** Uses the registry keys from Assignment 3 and `SharedState` in `split/guards.py`. The coordinator writes each accepted finding to a shared board using compare-and-set. The writer receives the version it was briefed with, and any write is rejected if the board version has changed.
  5. **Single trace:** All agents write to one trace through `ctx.agent`. Each line includes `agent` and `parent`; the coordinator's parent is `null`. The token counts across all agents add up to the `run_end` total.
  - **Guard replay results:** All three guard replays passed: deadlock detection 8/8, lost update 8/8, and combined result 8/8.

## Part C · Measured

**The five constants** (slide 59): model, tools, budget, evaluator, task set.

- **Model:** All 72 runs used `gpt-4.1-mini`.
- **Tools:** All runs used the same `schemas_sha` value (`703c0002892f27ec`).
- **Token budget:** Each issue had a limit of 250,000 tokens, as defined by `max_tokens` in `agent/bounds.yaml`. This gave each batch a total budget of 1,250,000 tokens. Arms S and M had the same token limit for each task. Arm S-plus used the average token spend of arm M for each task (`--match split`).
- **Evaluator:** All runs used the same `checks_sha` value (`55abcd67e6a3b208`). The reviewer was set to `scripted:approve-all`.
- **Task set:** All arms used the same eight tasks from `fixtures/tasks6`: batch-a, batch-b, one-4402, one-4403, one-4405, one-4406, one-4409, and one-4413.
- **Execution:** All arms ran with `--jobs 2`. No model call took more than 5.2 seconds. Therefore, rate-limit waits did not affect the wall-clock time of any arm.

**The results.**

| Arm | Kind | Passes / runs | Lowest and highest sweep | Tasks all three passed | Mean tokens | Mean wall-clock (s) |
|---|---|---|---|---|---|---|
| S | single | 12 / 18 | 3, 5 | 2 | 43,335 | 9.2 |
| S | batch | 0 / 6 (issues 22 / 30) | 0, 0 | 0 | 297,441 | 38.2 |
| M | single | 10 / 18 | 3, 4 | 3 | 27,662 | 10.6 |
| M | batch | 0 / 6 (issues 20 / 30) | 0, 0 | 0 | 146,700 | 14.1 |
| S-plus | single | 14 / 18 | 4, 5 | 4 | 28,384 | 10.0 |
| S-plus | batch | 0 / 6 (issues 24 / 30) | 0, 0 | 0 | 146,986 | 48.7 |

Passes for each task (of 3):

| Task | S | M | S-plus |
|---|---|---|---|
| one-4402 | 2 | 1 | 3 |
| one-4403 | 0 | 0 | 0 |
| one-4405 | 2 | 3 | 3 |
| one-4406 | 3 | 3 | 3 |
| one-4409 | 2 | 0 | 2 |
| one-4413 | 3 | 3 | 3 |
| batch-a | 0 | 0 | 0 |
| batch-b | 0 | 0 | 0 |

- Your multiplier (M over S), single and batch, beside the lecture's 15×:
  - **Token usage:** The split (M) used 0.64 times the tokens of one agent (S) on single tasks, and 0.49 times on batches. This shows that the split approach used fewer tokens than a single agent.
  - **Comparison with the lecture's 15× figure:** The 15× figure from the lecture measures typical token use for Anthropic's own work compared with a chat-based approach. In that comparison, one agent uses about 4× the tokens. My results measure something different: they compare two designs on the same task set. The split approach used fewer tokens for two reasons. First, each investigator has a smaller prompt and does not receive the schemas for the write tools. On single tasks, the investigator's first call carries about 2,030 tokens of context, against about 3,540 for arm S. This is the main saving on single tasks. Second, each context contains only one issue. In contrast, arm S handles all five issues in a single context during a batch. This adds to the saving on batches.
- Whether S-plus's spend matched M's in fact, task by task:
  - **Token usage:** Yes. S-plus used between 1.00 and 1.04 times the average token spend of arm M for each task. The ratios were: batch-a (1.00), batch-b (1.01), one-4402 (1.01), one-4403 (1.03), one-4405 (1.01), one-4406 (1.04), one-4409 (1.04), and one-4413 (1.03).
  - **Answer count:** Before reaching its token budget, S-plus gave 33 issues one answer and 15 issues two answers.
  - **What the vote did:** Almost nothing. With one answer, the vote has no choice. With two answers, a tie goes to the earliest answer, so the vote could never overrule the first attempt. In practice, S-plus was one read-only attempt in a fresh context, with code doing the writes. Thus, question 2 below (S against S-plus) compares two designs as well as two budgets: S-plus also had a smaller prompt, no write tools in its context, and a code-enforced stopping rule.

**Slide 18's three questions**, for each kind of task.

| Question | Single-issue results | Batch results |
|---|---|---|
| Did the split use more tokens? | No. M used 27,662 tokens, compared with 43,335 for S. This is 0.64 times the token usage of S. | No. M used 146,700 tokens, compared with 297,441 for S. This is 0.49 times the token usage of S. |
| Did higher token usage improve the score? | No. S used 43,335 tokens and passed 12 of 18 issues. S-plus used 28,384 tokens and passed 14 of 18 issues. | No. S used 297,441 tokens and passed 22 of 30 issues. S-plus used 146,986 tokens and passed 24 of 30 issues. Neither arm passed any of the six full batches. |
| Did one agent perform as well at the same budget? | Yes. S-plus passed 14 of 18 issues at approximately the same token budget as M. M passed 10 of 18. | Yes. S-plus passed 24 of 30 issues at approximately the same token budget as M. M passed 20 of 30. Neither arm passed any of the six full batches. |

**Noise.** Three sweeps cannot separate these pass counts. On single tasks the sweep ranges overlap: M passed 3 to 4 tasks in a sweep, S-plus 4 to 5, and S 3 to 5. The batch issue counts (20, 22 and 24 of 30) differ by two or four issues, which is also within what one sweep can change. Thus, the data supports "one agent did at least as well as the split", which is all that question 3 asks. It does not support "one agent passed more".

- What you would have claimed from arms S and M alone, and what you claim now:
- Based on the results from S and M alone, the split approach reduces token usage by about one third for single issues and one half for batches. It loses only 2 single runs and 2 batch issues. It also completes batches 2.7 times faster. These results initially suggest that the split approach is better suited for batch tasks.

- However, the split approach did not achieve a better score. With the same token budget, one agent did at least as well in both cases (S-plus 14 against 10 of 18 tasks, and 24 against 20 of 30 batch issues), though the gap is within the noise of three sweeps. The token savings came from giving each issue a separate context. A single agent can also use separate contexts for each issue at a lower cost (slide 12). Therefore, the split approach keeps only one clear advantage: shorter execution time for batches. It completed batches in 14.1 seconds, compared with 48.7 seconds for S-plus and 38.2 seconds for S. This improvement comes from parallel execution.

- My prediction was right on the batch multiplier (0.5; measured 0.49), on S-plus doing at least as well as M, and on batch speed (about 3×; measured 2.7×). It was wrong in three places: the single-task multiplier (predicted 1.3, measured 0.64), batch passes (I predicted M ahead of S, 24 vs 18 issues; M was behind, 20 vs 22), and full batches (no arm passed any). S's long batch context did not hurt it as I expected: it passed 73% of batch issues, against 67% of single issues.

**Every arm M run that failed.**
In all 14 runs, the coordinator waited for each investigator to finish before it started the writer. No wait cycle occurred. The only shared state was the findings board. The coordinator wrote to the board once for each issue, and the writer read it once. No write was rejected.

Each writer created the label, pull request, and comment exactly as described in its finding. The combined check passed in all 14 runs. This means the final state was consistent, but the finding itself was incorrect. The problem was not caused by an interaction between agents. Instead, one investigator made an error in its own part of the task in each run.

| Run | Files read and written | Cause of the error | Anomaly | MAST category |
|---|---|---|---|---|
| split-batch-a-s01-3cd2f9 | investigator-4420 read `src/api/errors.ts` and `src/api/auth.ts`. writer-4420 wrote the label `docs` and the file `src/api/auth.ts`. The other four lanes passed. | investigator-4420 identified the code that contains the password rule (`src/api/auth.ts`) instead of the document that describes the rule incorrectly (`docs/API.md`). It returned status `found`. | none | task_verification |
| split-batch-a-s02-e6b2c4 | investigator-4412 read `src/api/health.ts`. investigator-4420 read `src/api/auth.ts`. Both writers applied their findings. | investigator-4412 incorrectly classified a question as a bug. investigator-4420 made the same error as in s01. | none | task_verification |
| split-batch-a-s03-9f6246 | investigator-4412 read `src/api/health.ts`. investigator-4414 read `src/components/ReportTable.tsx`. investigator-4420 read `src/api/errors.ts` and `src/api/auth.ts`. | investigator-4412 incorrectly classified a question as a bug. investigator-4414 identified the table component instead of `src/api/reports.ts`. investigator-4420 made the same error as in s01. | none | task_verification |
| split-batch-b-s01-b7873e | investigator-4431 read `src/api/reports.ts`, `src/exportUtils.ts`, and `src/util/strings.ts`. writer-4431 wrote `bug` and `src/exportUtils.ts`. | investigator-4431 read the correct file (`src/util/strings.ts`), but identified its caller instead. It also incorrectly classified a feature request as a bug. | none | task_verification |
| split-batch-b-s02-2a5077 | investigator-4431 read `src/export/scheduler.ts`, `src/exportUtils.ts`, and `src/util/strings.ts`. investigator-4434 did not read any files during its 8 calls. | investigator-4431 made the same error as in s01. investigator-4434 used all 8 calls for searches without reading a file. It returned `bug`, `none`, and status `candidate`. The stopping rule caused this second error. | none | task_verification |
| split-batch-b-s03-a285f1 | investigator-4431 read the same three files as in s02. writer-4431 wrote `bug` and `src/exportUtils.ts`. | investigator-4431 made the same error as in s01. | none | task_verification |
| split-one-4402-s01-f40590 | investigator-4402 read `src/api/reports.ts` and `src/i18n/en.json`. writer-4402 wrote `bug` and `src/api/reports.ts`. | investigator-4402 followed the error key to the API instead of identifying the parser in `src/util/money.ts`. It returned status `found`. | none | task_verification |
| split-one-4402-s02-996507 | investigator-4402 read `src/api/reports.ts` and `src/db/repos/transactionRepo.ts`. writer-4402 wrote `bug` and `src/db/repos/transactionRepo.ts`. | investigator-4402 identified the repository code instead of `src/util/money.ts`. It returned status `found`. | none | task_verification |
| split-one-4403-s01-641ce5 | investigator-4403 read `src/export/csv.ts`. writer-4403 wrote `feature` and `src/export/csv.ts`. | investigator-4403 incorrectly classified a question about why a BOM appears as a feature request. It also provided a file. | none | task_verification |
| split-one-4403-s02-f72cbb | investigator-4403 read `src/export/csv.ts`. writer-4403 wrote `feature` and `src/export/csv.ts`. | investigator-4403 made the same error as in s01. | none | task_verification |
| split-one-4403-s03-f51ed9 | investigator-4403 read `src/export/csv.ts`. writer-4403 wrote `bug` and `src/export/csv.ts`. | investigator-4403 incorrectly classified the question as a bug. It also provided a file. | none | task_verification |
| split-one-4409-s01-993d4d | investigator-4409 read `docs/CONFIG.md` and then used all 8 calls. writer-4409 wrote `docs` and `docs/RUNNING_LOCALLY.md`. | The 8-call limit stopped the search. The investigator returned status `candidate` and named a file that does not exist and that it had not read. | none | system_design |
| split-one-4409-s02-a887ba | investigator-4409 read `docs/CONFIG.md`. writer-4409 wrote `docs` and `docs/setup.md`. | investigator-4409 returned status `found` and named `docs/setup.md`. This file does not exist, and the investigator had not read it. The return contract does not check whether the investigator read the file. | none | task_verification |
| split-one-4409-s03-441ee8 | investigator-4409 read `docs/CONFIG.md` and `src/config.ts`. writer-4409 wrote `docs` and `docs/CONFIG.md`. | investigator-4409 identified `docs/CONFIG.md` instead of `README.md`, which contains the local setup steps. | none | task_verification |

- **Task verification:** I gave 13 of the 14 runs the MAST category task verification, and one run system design. No agent checked whether the finding was correct. The return contract checks the format of the response, but it does not check its accuracy. The writer cannot inspect the code, so it cannot identify an incorrect finding.

- **Possible improvement:** A simple check could have caught two failures (4409 s01 and s02). The system could reject a return if the investigator did not read the file it named. However, this check would not guarantee that the finding itself was correct.
- **A gap between Part A and the build:** In Part A, gate 2 says the code can check that the investigator names a file it really read. I did not build that check: the contract validates only the form of a return, and that gap is what let 4409 s01 and s02 through.
- **The MAST label for batch-b s02:** In this run, investigator-4434 failed because of the 8-call limit, the same cause that I labelled system design for 4409 s01. I labelled the run by investigator-4431's error instead, because it is the same error as in batch-b s01 and s03, and it is task verification.

- **Comparison with one agent:** The same issues also failed when one agent handled them. Arm S failed issue 4420 in all three batch-a runs, issue 4431 in all three batch-b runs, and issue 4403 in all three runs for that task. This suggests that the failures came from the model's reasoning rather than from the split between agents.

## Part D · The decision

- **One agent for a single issue:** The split approach did not perform well. Gate 3 failed in the design review, and the results confirmed this. The split passed 10 of 18 tasks, compared with 12 of 18 for one agent. At the same token budget, one agent passed 14 of 18 tasks. These differences are within the noise of three sweeps, so the split did not beat one agent. The split was also slower, taking 10.6 seconds compared with 9.2 seconds for one agent.

- **One agent for a batch of five issues:** The split approach was faster and used fewer tokens than arm S. It completed the batch in 14.1 seconds, compared with 38.2 seconds for S. However, one agent at the same token budget did at least as well (24 of 30 issues compared with 20 of 30; the gap is within the noise of three sweeps). Neither approach passed a complete batch. Therefore, the main benefit of the split is shorter execution time. This benefit has little value for daily batch jobs that run in the background.

- **Conditions for reconsidering the decision:**
  1. **A test:** Build a batch task set where each issue has its own test: for example, five unrelated bug issues, each with a failing test in `fixtures/repo/test/` that passes only when the named file is fixed. Run the split and S-plus on it, three sweeps each, at the same budget. Reopen the decision for batches if the split passes more issues than S-plus in every sweep. A gap inside the sweep ranges, as in this measurement, does not count.
  2. **A requirement:** Reopen it if RepoMind gets a stated time limit for a batch that one agent cannot meet. In this measurement, S-plus took 48.7 seconds for a batch and the split took 14.1 seconds. Someone can test a stated limit with the same commands, by comparing each arm's mean wall-clock with it.
- **Looking back at the gates:** I passed gate 2 too generously. Part A says the code can check that the investigator names a file it really read, but I did not build that check, and no check of a finding's correctness exists for any issue. The decision record also finds that the batch only partly meets slide 49's condition. With what I know now, gate 2 is a fail for both kinds of task, and the gates alone would have chosen one agent. Gate 4 for the batch is "provisional" in this report. The JSON shows it as a plain pass because the JSON accepts only `pass`, `fail` or `not_reached`. I keep the Part A verdicts as I recorded them before I built anything.
- The record: `decisions/0006-topology.md`

## AI assistance

I used Claude Code to help implement the code and prepare the steps for running the tests. I wrote Part A and the initial predictions. Claude Code helped me correct formatting and grammar issues. It also helped populate `reports/LAB_06.json` using the data in `results/`. I wrote Parts B through D, `decisions/0006-topology.md`, and `CHANGES.md` based on the results. I then used Claude Code to review these documents. I ran all paid operations and Git commands myself. I also checked the reported numbers against `results/runs_06.jsonl`. Finally, `make test` passed, and `make check-06` returned 80/80 with no integrity flags.
