# FinSight / CFO Copilot - Candidate Data Pack (CSV only)

Every data file in this pack is a plain UTF-8 CSV with a header row. Open them with any spreadsheet tool, `pandas.read_csv`, `csv.DictReader`,
or load them straight into a database (`COPY` / `.import`). Text fields that contain line breaks (filing text, prompts) are quoted per the CSV standard,
so use a real CSV parser, not line-by-line splitting. A full column list is in `data_dictionary.csv`.

All companies, filings and figures are FICTIONAL and were produced for this exercise. The data comes from an automated extraction process and has NOT
been cleaned for you. Treat it the way you would treat data from an outside vendor.

| File | Used for | What it is |
| --- | --- | --- |
| `puzzle1_data/financial_statements_raw.csv` | Puzzle 1 | Extracted financial statement lines for 5 companies across 12 fiscal quarters (1,449 rows) |
| `puzzle1_data/filings_index.csv` | Puzzle 1 | One row per filing: id, form type, period, filing date, reporting unit. `doc_id` links to the corpus |
| `puzzle1_data/companies.csv` | Puzzle 1 | Company reference list |
| `puzzle1_data/kpi_glossary.csv` | Puzzle 1 | The 16 KPIs your platform must compute, with exact formulas |
| `puzzle1_data/corpus_documents.csv` | RAG, all puzzles | 64 documents (filing text and other documents), one row per document, full text in the `text` column |
| `puzzle2_data/request_log.csv` | Puzzle 2 | 220 requests logged by a chatbot someone else built. One column per prompt segment, in the order the prompt was assembled |
| `puzzle2_data/reference_hardware_and_model.csv` | Puzzle 2 | GPU and reference-model figures for budgeting |
| `puzzle3_data/starter_test_cases.csv` | Puzzle 3 | 12 starter test cases showing the format. You must build 40 or more of your own |
| `puzzle4_data/dev_questions.csv` | Puzzles 3, 4, 5 | 21 development questions with expected route and answer. Your own evalset and golden set must be larger |
| `data_dictionary.csv` | All | Every file, every column, what it means |

## Notes
- Sign conventions, labels, units and date formats are as extracted. Documenting and handling them is part of your job.
- The `kpi_glossary.csv` formulas are authoritative for this project.
- The hidden evaluation set is larger than the development set and is not in this pack.
- Reference hardware figures are for budgeting only.
