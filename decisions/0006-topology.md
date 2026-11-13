# 0006 · Topology: One Agent for Single Issues and Batches

**Status:** Decided, 2026-11-13. Assignment 6.

## Context

RepoMind currently handles its daily tasks with one agent. The agent reads an issue, searches the code, applies a label, opens a draft pull request when a file is responsible, and posts a comment. This record examines whether one agent should be replaced with multiple agents. Lecture 6 states that the second agent must provide a clear benefit to justify its addition (slide 8).

I implemented a split design on the `lab-06-split` branch (tag `lab-06-split-final`). I have not merged this branch. The design uses a coordinator and two roles. Each role has access to a different set of tools:

- **Investigator:** Each issue has its own investigator. It can use read tools and a return tool, but it cannot write to the repository.
- **Writer:** Each issue has its own writer. It can use only `issues_label`, `pulls_open`, and `issues_comment`.
- **Batch execution:** All five lanes run at the same time.

## The gates and the prediction (Part A)

I used the four gates from slide 46 to evaluate the split design.

| Gate (slide 46) | One issue | A batch of five |
|---|---|---|
| 1. The parts can work mostly independently | pass | pass |
| 2. Each part's result can be checked separately | pass | pass |
| 3. The team provides a benefit that one agent cannot achieve at a lower cost | fail | pass (parallelism) |
| 4. The result justifies the additional cost | not reached | pass, provisional |

Looking back, I passed gate 2 too generously. I said the code could check that the investigator names a file it really read, but I did not build that check, and no check of a finding's correctness exists for any issue. With what I know now, gate 2 is a fail for both kinds of task, and the gates alone would have chosen one agent. I keep the verdicts above as I recorded them before I built anything. (`reports/LAB_06.json` shows gate 4 for the batch as a plain `pass`, because it accepts only `pass`, `fail` or `not_reached`.)

Before running the split, I recorded my predictions in `reports/PREDICTIONS_06.md` (commit `946e454`).

My predictions were:

- **Single tasks:** M would use about 1.3 times as many tokens as S. S would pass about 12 of 18 tasks, while M would pass about 11 of 18. S-plus would pass at least as many tasks as M.
- **Batch tasks:** M would use about 0.5 times as many tokens as S. M would pass a few more issues (24 of 30 compared with 18 of 30). S-plus would pass as many tasks as M.
- **Expected decision:** Keep one agent for both types of tasks unless the split performs better than S-plus at the same token budget.

## What I measured (Part C)

I kept the following five settings the same across all 72 runs:

- **Model:** All runs used `gpt-4.1-mini`.
- **Tools:** All runs used the same `schemas_sha` value: `703c0002892f27ec`.
- **Token budget:** Each issue had a limit of 250,000 tokens (B), for a total of 1,250,000 tokens per batch. S-plus used the average token spend of M for each task.
- **Evaluator:** All runs used the same `checks_sha` value: `55abcd67e6a3b208`. The reviewer was set to `scripted:approve-all`.
- **Task set:** All runs used the eight tasks in `fixtures/tasks6`.

My original prediction used `ministral-14b-2512`. However, its API key allowed only two requests per minute. I therefore changed the model before starting the first measured run.

The results were:

| Arm | Kind | Passes / runs | Issues | Mean tokens | Mean wall-clock (s) |
|---|---|---|---|---|---|
| S (one agent) | single | 12 / 18 | 12 / 18 | 43,335 | 9.2 |
| S (one agent) | batch | 0 / 6 | 22 / 30 | 297,441 | 38.2 |
| M (split) | single | 10 / 18 | 10 / 18 | 27,662 | 10.6 |
| M (split) | batch | 0 / 6 | 20 / 30 | 146,700 | 14.1 |
| S-plus (one agent, spend of M) | single | 14 / 18 | 14 / 18 | 28,384 | 10.0 |
| S-plus (one agent, spend of M) | batch | 0 / 6 | 24 / 30 | 146,986 | 48.7 |

The token multiplier (M compared with S) was 0.64 for single tasks and 0.49 for batches. This means the split used fewer tokens than one agent in both cases.

The lecture reports a 15× multiplier for multi-agent systems compared with a chat-based approach. My measurement uses a different comparison: it compares two designs with one agent on the same task set. In my results, the split used fewer tokens.

S-plus used between 1.00 and 1.04 times the average token spend of M for each task.

### Slide 18: Three questions

I used the three questions from slide 18 to compare the results.

| Question | One issue | A batch of five |
|---|---|---|
| Did the split use more tokens? | No. M used 0.64 times the tokens used by S. | No. M used 0.49 times the tokens used by S. |
| Did higher token usage improve the score? | No. S used 43,335 tokens and passed 12 of 18 tasks. S-plus used 28,384 tokens and passed 14 of 18. | No. S used 297,441 tokens and passed 22 of 30 issues. S-plus used 146,986 tokens and passed 24 of 30. |
| Did one agent perform as well at the same budget? | Yes. S-plus passed 14 of 18 tasks, while M passed 10 of 18. | Yes. S-plus passed 24 of 30 issues, while M passed 20 of 30. |

None of the arms passed a complete batch.

Two limits on these answers:

- **Noise:** Three sweeps cannot separate the pass counts. On single tasks the sweep ranges overlap (M 3 to 4 tasks in a sweep, S-plus 4 to 5, S 3 to 5), and the batch issue counts differ by only two or four of 30. The data supports "one agent did at least as well as the split", not "one agent passed more".
- **The S-plus vote:** S-plus gave 33 issues one answer and 15 issues two. A tie goes to the earliest answer, so the vote could never overrule the first attempt. In practice, S-plus was one read-only attempt in a fresh context, with code doing the writes. Thus, question 2 (S against S-plus) compares two designs as well as two budgets.

### Failure analysis

I reviewed all 14 failed runs of M. None had an anomaly between agents. In each run, an investigator returned an incorrect label or file, and its writer applied that finding as instructed.

The combined check passed in all 14 runs. I gave 13 failures the MAST category task verification, and one system design.

The same issues also failed when one agent handled them. This indicates that the main problem was the investigator's finding, not communication between agents.

## The decision

- **One issue: Keep one agent.** The split did not beat one agent, either at one agent's own budget (10 against 12 of 18) or at the split's budget (10 against 14 of 18). These gaps are within the noise of three sweeps. It also took longer to finish. Therefore, the split provided no clear benefit for single issues.

- **A batch of five: Keep one agent.** The split used fewer tokens and completed the batch 2.7 times faster than S. It took 14.1 seconds, compared with 38.2 seconds for S. However, one agent at the same token budget did at least as well (24 of 30 issues compared with 20 of 30; the gap is within the noise of three sweeps). Neither approach passed a complete batch. The main benefit of the split was shorter execution time. This benefit has limited value for a daily batch that runs in the background.

- **Overall decision:** RepoMind will continue to use one agent in this repository. I have not merged the split branch.

## The condition for reconsidering the decision

I would reconsider the decision for batch tasks if either of the following conditions is met:

1. **A test:** Build a batch task set where each issue has its own test: for example, five unrelated bug issues, each with a failing test in `fixtures/repo/test/` that passes only when the named file is fixed. Run the split and S-plus on it at the same budget, three sweeps each. Reopen the decision for batches if the split passes more issues than S-plus in every sweep. A gap inside the sweep ranges, as in this measurement, does not count.

   Anyone can run this test with the following commands, with `<tasks>` set to that task set and `<B>` to 250,000:

   `python run.py --tasks <tasks> --way split --budget <B> --runs 3`

   `python run.py --tasks <tasks> --way splus --match split --runs 3`

   `python eval/results_06.py`

2. **A requirement:** Reopen the decision if RepoMind gets a stated time limit for a batch that one agent cannot meet. In this measurement, S-plus took 48.7 seconds for a batch and the split took 14.1 seconds. Someone can test a stated limit with the same commands, by comparing each arm's mean wall-clock with it.

### How my results compare with slide 49

Slide 49 describes a batch of separate issues. Each issue must have its own test, and all issues must run at the same time.

My batch experiment meets two of these conditions:

- Each batch contains separate issues.
- All five lanes run at the same time.

However, it does not meet the requirement that each issue has its own test. A triage finding does not have a separate test. The combined check verifies the format of the final state, but it does not verify whether the label and file are correct.

Therefore, my batch results only partially satisfy the condition from slide 49.

A different experiment could produce a different result. For example, each issue could have its own failing test to verify the investigator's finding.

## What each design gives up

### If we use multiple agents

The split design has three main disadvantages:

- **Score:** At the same token budget, the split did no better than one agent, and passed fewer tasks in this measurement (within the noise of three sweeps).
- **Information:** The writer cannot read the code. It can only use the information returned by the investigator. If the investigator makes an incorrect finding or leaves out important information, the writer cannot detect the problem.
- **Simplicity:** The split requires a coordinator, two prompts, a return contract, and five checks. All these parts require maintenance.

### If we keep one agent

Keeping one agent also has some disadvantages:

- **Wall-clock time:** One agent takes longer to complete a batch. The split took 14.1 seconds, compared with 38.2 seconds for S and 48.7 seconds for S-plus.
- **Tool restrictions:** The split gives the investigator access only to read tools until it returns a finding. One agent can get most of this benefit by changing its available tools at each stage of the task.

## Final decision

RepoMind will continue to use one agent for both single issues and batches. The split implementation remains on `lab-06-split` and is not merged. This record documents the results and the reasons for keeping the current design.

`ARCHITECTURE.md` remains unchanged: RepoMind stays one agent, and this record is the result.