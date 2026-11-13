# Assignment 6 · Predictions, written before any run of the split

Model: Mistral, ministral-14b-2512.

Budget B: 250,000 tokens for each issue (max_tokens in agent/bounds.yaml). A batch gets 5B.

## The split that I will make

A coordinator controls the run. The coordinator is code, and it does not use a model.

Each issue gets one investigator. The investigator has only the read tools: issues_read,
code_search, code_read_file and code_run_tests.

Each issue gets one writer. The writer has only the write tools: issues_label, pulls_open and
issues_comment.

In a batch, the five investigators operate at the same time.

## Single tasks (6 tasks, 3 sweeps, 18 runs for each arm)

1. Tokens: arm M uses approximately 1.3 times the tokens of arm S for each task. The range is
   1.1 to 1.6 times. The writer has a second context with its own prompt, tool schemas and
   brief. The investigator does not get the schemas of the write tools, but this saves only a
   small quantity of tokens.
2. Passes: arm S and arm M pass approximately the same number of tasks. Arm S gets
   approximately 12 of 18. Arm M gets approximately 11 of 18. The difference is not more than
   2 runs. One issue gives the split no parts that operate at the same time. The writer cannot
   read the code, thus the writer loses all data that the investigator does not return.
3. Arm S-plus: one agent with the budget that arm M used. Arm S-plus passes at least as many
   tasks as arm M, approximately 12 of 18. One more attempt and a vote give the single agent
   all that the split gets.

## Batch tasks (2 tasks, 3 sweeps, 6 runs for each arm, 30 issues)

1. Tokens: arm M uses approximately 0.5 times the tokens of arm S for each task. The range is
   0.3 to 0.8 times. Arm S does the five issues in one context. Thus, each new call reads all
   the earlier issues again. In the split, each context holds only one issue.
2. Passes: arm M passes a few more than arm S. A batch passes only when all five issues pass.
   Thus, a full pass is not frequent for the two arms. For full tasks, arm S gets
   approximately 1 of 6 and arm M gets approximately 2 of 6. For issues, arm S gets
   approximately 18 of 30 and arm M gets approximately 24 of 30. Arm S does its last issues
   in a long context that holds much unrelated data. Thus, arm S passes fewer of its batch
   issues than of its single issues.
3. Arm S-plus: arm S-plus passes as many tasks as arm M, approximately 2 of 6 and 24 of 30.
   Arm S-plus gets the smaller budget of arm M. It gives each issue a new context. Thus, one
   agent gets the benefit of context isolation (slide 12). The split keeps only one benefit:
   time. The split is approximately 3 times faster, because the investigators operate at the
   same time.

## The decision that I expect

For single issues, I expect to keep one agent.

For batches, I also expect to keep one agent. The split must do better than arm S-plus at the
same budget to change this decision.

Less time alone has a small value for a daily batch that operates in the background.
