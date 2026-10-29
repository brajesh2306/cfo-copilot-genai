# THE TWIST - Drop 2 (released end of Day 2, you have 24 hours)

Four things changed. Adapt your system, then hand in a short diff note.

## 1. A sixth company
Zephyr Logistics Ltd. (ZLG) joins the CFO's coverage list. See the files in `data/`. It has its own fiscal calendar.
Add it through a proper schema migration, not by editing tables by hand.

## 2. A filing amendment
the document `NWI-10QA-FY2024Q3` in `data/corpus_documents_new.csv` and the matching rows in `data/financial_statements_raw_new.csv` amend a quarter already in your database.
Decide how your policy handles it, and show that earlier answers change (or do not change) for the reason your policy says.

## 3. Longer contexts
The CFO now wants whole filings in context. Your maximum context length rises from **4,096 to 8,192 tokens**. GPU (6 GB), concurrency target and p95 TTFT target are unchanged.
Show what you gave up to stay inside the budget.

## 4. A new product requirement: confidence
Every answer must now carry a `confidence` level (`high`, `medium`, `low`) and a short `confidence_basis`, **derived from evidence in your pipeline**
(for example provenance, agreement between sources, retrieval scores, whether a policy choice affects the answer), not from the model grading itself.
`low` confidence answers on numbers must either be withheld or clearly marked. Document your rule and test it.

## Diff note (hand in with the updated system)
What changed, how many files you touched, what broke, what that tells you about your architecture, and what you would redesign.
