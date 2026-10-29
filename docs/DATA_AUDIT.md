# Initial supplied-data audit

- Candidate pack states that all company names/figures are fictional and that source CSVs are intentionally unclean.
- Initial financial statement file: 1,449 rows across five companies and 12 distinct fiscal-year/quarter combinations.
- Candidate pack includes 64 filing/document records, 16 authoritative KPI definitions, 12 starter model test cases and 21 agent development questions.
- Drop 2 adds Zephyr Logistics (ZLG), a set of ZLG filings/statement rows, and the NWI FY2024 Q3 amendment `NWI-10QA-FY2024Q3`.
- Ingestion preserves raw values/units and stores normalized USD values. Unit conversion currently recognizes `USD`, `USD_thousands`, and `USD_millions`.
- Unknown line-item labels remain unmapped. Alias coverage must be audited before claiming all KPI values are correct.
- Latest filing date currently takes precedence per canonical item and period. This policy needs explicit regression tests, especially for the amendment and comparable periods.
