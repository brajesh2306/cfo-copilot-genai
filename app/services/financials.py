from __future__ import annotations

import os
import hashlib
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv


BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE.parent / ".env")
DATA = BASE / "data"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://cfo_user:cfo_password_change_me@127.0.0.1:3306/cfo_copilot",
)

_engine = None


def get_engine():
    """Create and return the configured MySQL engine."""
    global _engine

    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=1800,
        )

    return _engine


def database_initialized():
    """Check whether the database is reachable and initialized."""
    try:
        with get_engine().connect() as con:
            con.execute(text("SELECT 1 FROM companies LIMIT 1"))
        return True
    except Exception:
        return False


# Canonical mappings are explicit. Unknown labels are not guessed.
ALIASES = {
    "revenue": {
        "revenue",
        "revenues",
        "total revenues",
        "net sales",
    },
    "gross_profit": {
        "gross profit",
        "gross margin",
    },
    "operating_income": {
        "operating income",
        "operating profit",
        "income (loss) from operations",
    },
    "net_income": {
        "net income",
        "net earnings",
        "net income (loss)",
    },
    "depreciation_and_amortization": {
        "depreciation and amortization",
    },
    "total_current_assets": {
        "total current assets",
    },
    "total_current_liabilities": {
        "total current liabilities",
    },
    "total_debt": {
        "total debt",
    },
    "total_equity": {
        "total stockholders' equity",
        "total equity",
        "total shareholders’ equity",
        "total shareholders equity",
    },
    "cash_from_operations": {
        "net cash provided by operating activities",
        "cash from operating activities",
    },
    "capital_expenditures": {
        "purchases of property and equipment",
        "capital expenditures",
        "capital expenditure",
    },
    "total_assets": {
        "total assets",
    },
    "research_and_development": {
        "research and development",
        "technology and development",
    },
    "sales_and_marketing": {
        "sales and marketing",
        "marketing expense",
        "selling and marketing",
        "store operating and marketing",
    },
    "general_and_administrative": {
        "general and administrative",
        "corporate general and administrative",
    },
    "interest_expense": {
        "interest expense",
        "interest expense, net",
    },
}

ALIAS_LOOKUP = {
    alias: canonical
    for canonical, aliases in ALIASES.items()
    for alias in aliases
}


def canonical_item(label: str) -> Optional[str]:
    """Map a raw financial statement label to its canonical item."""
    normalized = " ".join(str(label).strip().lower().split())
    return ALIAS_LOOKUP.get(normalized)


def to_usd(value, unit):
    """Convert supported USD units to whole USD."""
    unit = str(unit).strip().lower()

    factors = {
        "usd": 1.0,
        "usd_thousands": 1_000.0,
        "usd_millions": 1_000_000.0,
    }

    factor = factors.get(unit)

    if factor is None:
        return None

    return float(value) * factor


def connect():
    """Return a SQLAlchemy connection to the configured MySQL database."""
    # Fix: initialize the engine before opening a connection.
    return get_engine().connect()


def initialize_db():
    """Run the initial SQL migration."""
    migration = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "001_initial.sql"
    )

    statements = [
        part.strip()
        for part in migration.read_text().split(";")
        if part.strip()
    ]

    with get_engine().begin() as con:
        for statement in statements:
            con.execute(text(statement))


def _read_csv(rel):
    """Read a project CSV while preserving its original text values."""
    return pd.read_csv(
        DATA / rel,
        dtype=str,
        keep_default_na=False,
    )


def ingest_all():
    """
    Ingest candidate-pack and Drop 2 data.

    Existing records are updated by their stable IDs, while document
    chunks are inserted only if their chunk IDs do not already exist.
    """
    initialize_db()

    companies = _read_csv("puzzle1_data/companies.csv")
    filings = _read_csv("puzzle1_data/filings_index.csv")
    lines = _read_csv("puzzle1_data/financial_statements_raw.csv")
    glossary = _read_csv("puzzle1_data/kpi_glossary.csv")
    docs = _read_csv("puzzle1_data/corpus_documents.csv")

    # Merge Drop 2 records without duplicating their stable identifiers.
    drop = DATA / "drop2" / "data"

    if (drop / "companies_new.csv").exists():
        companies = (
            pd.concat(
                [
                    companies,
                    pd.read_csv(
                        drop / "companies_new.csv",
                        dtype=str,
                        keep_default_na=False,
                    ),
                ],
                ignore_index=True,
            )
            .drop_duplicates("company_id", keep="last")
        )

        filings = (
            pd.concat(
                [
                    filings,
                    pd.read_csv(
                        drop / "filings_index_new.csv",
                        dtype=str,
                        keep_default_na=False,
                    ),
                ],
                ignore_index=True,
            )
            .drop_duplicates("filing_id", keep="last")
        )

        lines = (
            pd.concat(
                [
                    lines,
                    pd.read_csv(
                        drop / "financial_statements_raw_new.csv",
                        dtype=str,
                        keep_default_na=False,
                    ),
                ],
                ignore_index=True,
            )
            .drop_duplicates("row_id", keep="last")
        )

        docs = (
            pd.concat(
                [
                    docs,
                    pd.read_csv(
                        drop / "corpus_documents_new.csv",
                        dtype=str,
                        keep_default_na=False,
                    ),
                ],
                ignore_index=True,
            )
            .drop_duplicates("doc_id", keep="last")
        )

    with get_engine().begin() as con:
        # Companies
        con.execute(
            text(
                """
                INSERT INTO companies
                    (company_id, name, sector, reporting_currency,
                     fiscal_year_note)
                VALUES
                    (:company_id, :name, :sector, :reporting_currency,
                     :fiscal_year_note)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    sector = VALUES(sector),
                    reporting_currency = VALUES(reporting_currency),
                    fiscal_year_note = VALUES(fiscal_year_note)
                """
            ),
            companies[
                [
                    "company_id",
                    "name",
                    "sector",
                    "reporting_currency",
                    "fiscal_year_note",
                ]
            ].to_dict("records"),
        )

        # Filings
        for _, row in filings.iterrows():
            form_type = str(row.form_type).upper()
            filing_id = str(row.filing_id).upper()

            is_amendment = int(
                "/A" in form_type or "10QA" in filing_id
            )

            con.execute(
                text(
                    """
                    INSERT INTO filings
                        (filing_id, company_id, form_type, fiscal_year,
                         fiscal_quarter, period_end, filed_date, doc_id,
                         reporting_unit, is_amendment)
                    VALUES
                        (:filing_id, :company_id, :form_type, :fiscal_year,
                         :fiscal_quarter, :period_end, :filed_date, :doc_id,
                         :reporting_unit, :is_amendment)
                    ON DUPLICATE KEY UPDATE
                        company_id = VALUES(company_id),
                        form_type = VALUES(form_type),
                        fiscal_year = VALUES(fiscal_year),
                        fiscal_quarter = VALUES(fiscal_quarter),
                        period_end = VALUES(period_end),
                        filed_date = VALUES(filed_date),
                        doc_id = VALUES(doc_id),
                        reporting_unit = VALUES(reporting_unit),
                        is_amendment = VALUES(is_amendment)
                    """
                ),
                {
                    "filing_id": row.filing_id,
                    "company_id": row.company_id,
                    "form_type": row.form_type,
                    "fiscal_year": int(row.fiscal_year),
                    "fiscal_quarter": int(row.fiscal_quarter),
                    "period_end": row.period_end,
                    "filed_date": row.filed_date,
                    "doc_id": row.doc_id,
                    "reporting_unit": row.reporting_unit,
                    "is_amendment": is_amendment,
                },
            )

        # Financial statement lines
        for _, row in lines.iterrows():
            value = pd.to_numeric(
                pd.Series([row.value]),
                errors="coerce",
            ).iloc[0]

            if pd.isna(value):
                continue

            con.execute(
                text(
                    """
                    INSERT INTO statement_lines
                        (row_id, company_id, filing_id, statement,
                         line_item_raw, canonical_item, fiscal_year,
                         fiscal_quarter, period_start, period_end,
                         raw_value, raw_unit, currency, value_usd,
                         source_status)
                    VALUES
                        (:row_id, :company_id, :filing_id, :statement,
                         :line_item_raw, :canonical_item, :fiscal_year,
                         :fiscal_quarter, :period_start, :period_end,
                         :raw_value, :raw_unit, :currency, :value_usd,
                         :source_status)
                    ON DUPLICATE KEY UPDATE
                        value_usd = VALUES(value_usd),
                        canonical_item = VALUES(canonical_item)
                    """
                ),
                {
                    "row_id": row.row_id,
                    "company_id": row.company_id,
                    "filing_id": row.filing_id,
                    "statement": row.statement,
                    "line_item_raw": row.line_item_raw,
                    "canonical_item": canonical_item(row.line_item_raw),
                    "fiscal_year": int(row.fiscal_year),
                    "fiscal_quarter": int(row.fiscal_quarter),
                    "period_start": row.period_start,
                    "period_end": row.period_end,
                    "raw_value": float(value),
                    "raw_unit": row.unit,
                    "currency": row.currency,
                    "value_usd": to_usd(value, row.unit),
                    "source_status": "ingested",
                },
            )

        # KPI glossary
        con.execute(
            text(
                """
                INSERT INTO kpi_definitions
                    (kpi_id, kpi_name, formula, unit, notes)
                VALUES
                    (:kpi_id, :kpi_name, :formula, :unit, :notes)
                ON DUPLICATE KEY UPDATE
                    kpi_name = VALUES(kpi_name),
                    formula = VALUES(formula),
                    unit = VALUES(unit),
                    notes = VALUES(notes)
                """
            ),
            glossary[
                ["kpi_id", "kpi_name", "formula", "unit", "notes"]
            ].to_dict("records"),
        )

        # Split documents into deterministic, repeatable chunks.
        for _, doc in docs.iterrows():
            content = str(doc.text)
            paragraphs = [
                part.strip()
                for part in content.split("\n\n")
                if part.strip()
            ]

            chunks = []
            current = ""

            for paragraph in paragraphs:
                if len(current) + len(paragraph) > 1800 and current:
                    chunks.append(current)
                    current = paragraph
                else:
                    current = (current + "\n\n" + paragraph).strip()

            if current:
                chunks.append(current)

            for index, chunk in enumerate(chunks):
                content_hash = hashlib.sha256(
                    chunk.encode()
                ).hexdigest()

                chunk_id = f"{doc.doc_id}#c{index}"

                con.execute(
                    text(
                        """
                        INSERT IGNORE INTO document_chunks
                            (chunk_id, doc_id, company_id, filing_id,
                             chunk_index, text, content_hash)
                        VALUES
                            (:chunk_id, :doc_id, :company_id, :filing_id,
                             :chunk_index, :text, :content_hash)
                        """
                    ),
                    {
                        "chunk_id": chunk_id,
                        "doc_id": doc.doc_id,
                        "company_id": doc.company_id,
                        "filing_id": doc.doc_id,
                        "chunk_index": index,
                        "text": chunk,
                        "content_hash": content_hash,
                    },
                )


def list_companies():
    """Return all companies."""
    with connect() as con:
        return pd.read_sql_query(
            text("SELECT * FROM companies ORDER BY company_id"),
            con,
        )


def list_periods(company_id):
    """Return the available fiscal periods for a company."""
    with connect() as con:
        return pd.read_sql_query(
            text(
                """
                SELECT DISTINCT fiscal_year, fiscal_quarter
                FROM statement_lines
                WHERE company_id = :company_id
                ORDER BY fiscal_year, fiscal_quarter
                """
            ),
            con,
            params={"company_id": company_id},
        )


def source_values(company_id, year, quarter):
    """Fetch period-specific financial values with filing provenance."""
    with connect() as con:
        return pd.read_sql_query(
            text(
                """
                SELECT
                    s.row_id,
                    s.filing_id,
                    s.statement,
                    s.line_item_raw,
                    s.canonical_item,
                    s.value_usd,
                    s.raw_value,
                    s.raw_unit,
                    s.period_end,
                    f.filed_date,
                    f.is_amendment
                FROM statement_lines s
                JOIN filings f USING (filing_id)
                WHERE s.company_id = :company_id
                  AND s.fiscal_year = :year
                  AND s.fiscal_quarter = :quarter
                ORDER BY f.filed_date DESC
                """
            ),
            con,
            params={
                "company_id": company_id,
                "year": int(year),
                "quarter": int(quarter),
            },
        )


def free_cash_flow(values, sources):
    """
    Free cash flow = operating cash flow - absolute capital expenditures.
    Capex is treated as a positive outflow amount.
    """
    required = {"cash_from_operations", "capital_expenditures"}

    if not required.issubset(values):
        return None, []

    value = (
        values["cash_from_operations"]
        - abs(values["capital_expenditures"])
    )

    rows = [
        sources["cash_from_operations"],
        sources["capital_expenditures"],
    ]

    return value, rows


def compute_kpis(company_id, year, quarter):
    """
    Compute the 16 defined KPIs from financial statement data.

    Conflict policy: the latest filed source line wins for each canonical
    item in the selected fiscal period. Missing inputs are not guessed.
    KPI values retain the IDs of the source rows used in their calculation.
    """
    df = source_values(company_id, year, quarter)

    chosen = {}

    for _, row in df.iterrows():
        key = row.canonical_item

        if not key or pd.isna(row.value_usd):
            continue

        # The query sorts newest filing first, so the first row wins.
        if key not in chosen:
            chosen[key] = row

    values = {
        key: float(row.value_usd)
        for key, row in chosen.items()
    }

    sources = {
        key: str(row.row_id)
        for key, row in chosen.items()
    }

    def ratio(numerator, denominator, multiplier=1):
        if numerator not in values or denominator not in values:
            return None, []

        denominator_value = values[denominator]

        if denominator == "interest_expense":
            denominator_value = abs(denominator_value)

        if denominator_value == 0:
            return None, []

        result = (
            values[numerator] / denominator_value
        ) * multiplier

        return result, [
            sources[numerator],
            sources[denominator],
        ]

        return result, [
            sources[numerator],
            sources[denominator],
        ]

    results = []

    def add(kpi_id, name, value, row_ids, unit):
        available = value is not None and bool(row_ids)

        results.append(
            {
                "kpi_id": kpi_id,
                "kpi_name": name,
                "value": value,
                "unit": unit,
                "status": (
                    "available" if value is not None else "missing_input"
                ),
                "source_row_ids": row_ids,
                "confidence": "high" if available else "low",
                "confidence_basis": (
                    "Required source line items are present and traceable."
                    if available
                    else "One or more required source line items are missing."
                ),
            }
        )

    # Margin and balance-sheet/operating ratios.
    ratio_definitions = [
        (
            "gross_margin_pct",
            "Gross margin",
            "gross_profit",
            "revenue",
            100,
            "%",
        ),
        (
            "operating_margin_pct",
            "Operating margin",
            "operating_income",
            "revenue",
            100,
            "%",
        ),
        (
            "net_margin_pct",
            "Net margin",
            "net_income",
            "revenue",
            100,
            "%",
        ),
        (
            "current_ratio_x",
            "Current ratio",
            "total_current_assets",
            "total_current_liabilities",
            1,
            "x",
        ),
        (
            "debt_to_equity_x",
            "Debt to equity",
            "total_debt",
            "total_equity",
            1,
            "x",
        ),
        (
            "roe_quarterly_pct",
            "Return on equity (quarterly)",
            "net_income",
            "total_equity",
            100,
            "%",
        ),
        (
            "interest_coverage_x",
            "Interest coverage",
            "operating_income",
            "interest_expense",
            1,
            "x",
        ),
        (
            "asset_turnover_x",
            "Asset turnover (quarterly)",
            "revenue",
            "total_assets",
            1,
            "x",
        ),
        (
            "rd_intensity_pct",
            "R&D intensity",
            "research_and_development",
            "revenue",
            100,
            "%",
        ),
    ]

    for kpi_id, name, numerator, denominator, multiplier, unit in ratio_definitions:
        value, row_ids = ratio(
            numerator,
            denominator,
            multiplier,
        )

        add(kpi_id, name, value, row_ids, unit)

    # Free cash flow and FCF margin.
    fcf, fcf_rows = free_cash_flow(values, sources)

    add(
        "free_cash_flow_usd",
        "Free cash flow",
        fcf,
        fcf_rows,
        "USD",
    )

    if (
        fcf is not None
        and "revenue" in values
        and values["revenue"] != 0
    ):
        fcf_margin = fcf / values["revenue"] * 100
        fcf_margin_rows = fcf_rows + [sources["revenue"]]
    else:
        fcf_margin = None
        fcf_margin_rows = []

    add(
        "fcf_margin_pct",
        "Free cash flow margin",
        fcf_margin,
        fcf_margin_rows,
        "%",
    )

    # EBITDA = operating income + depreciation and amortization.
    if (
        "operating_income" in values
        and "depreciation_and_amortization" in values
    ):
        ebitda = (
            values["operating_income"]
            + values["depreciation_and_amortization"]
        )

        ebitda_rows = [
            sources["operating_income"],
            sources["depreciation_and_amortization"],
        ]
    else:
        ebitda = None
        ebitda_rows = []

    add(
        "ebitda_usd",
        "EBITDA",
        ebitda,
        ebitda_rows,
        "USD",
    )

    if (
        ebitda is not None
        and "revenue" in values
        and values["revenue"] != 0
    ):
        ebitda_margin = ebitda / values["revenue"] * 100
        ebitda_margin_rows = ebitda_rows + [sources["revenue"]]
    else:
        ebitda_margin = None
        ebitda_margin_rows = []

    add(
        "ebitda_margin_pct",
        "EBITDA margin",
        ebitda_margin,
        ebitda_margin_rows,
        "%",
    )

    # Operating expense ratio excludes restructuring.
    opex_keys = [
        "research_and_development",
        "sales_and_marketing",
        "general_and_administrative",
    ]

    if (
        all(key in values for key in opex_keys)
        and "revenue" in values
        and values["revenue"] != 0
    ):
        opex = (
            sum(values[key] for key in opex_keys)
            / values["revenue"]
            * 100
        )

        opex_rows = (
            [sources[key] for key in opex_keys]
            + [sources["revenue"]]
        )
    else:
        opex = None
        opex_rows = []

    add(
        "opex_ratio_pct",
        "Operating expense ratio",
        opex,
        opex_rows,
        "%",
    )

    # Working capital = current assets - current liabilities.
    if (
        "total_current_assets" in values
        and "total_current_liabilities" in values
    ):
        working_capital = (
            values["total_current_assets"]
            - values["total_current_liabilities"]
        )

        working_capital_rows = [
            sources["total_current_assets"],
            sources["total_current_liabilities"],
        ]
    else:
        working_capital = None
        working_capital_rows = []

    add(
        "working_capital_usd",
        "Working capital",
        working_capital,
        working_capital_rows,
        "USD",
    )

    # Revenue YoY growth: same fiscal quarter in the prior fiscal year.
    yoy_growth = None
    yoy_rows = []

    if "revenue" in values:
        prior_df = source_values(
            company_id,
            int(year) - 1,
            quarter,
        )

        prior_revenue_row = None

        for _, prior_row in prior_df.iterrows():
            if (
                prior_row.canonical_item == "revenue"
                and pd.notna(prior_row.value_usd)
            ):
                prior_revenue_row = prior_row
                break

        if prior_revenue_row is not None:
            prior_revenue = float(prior_revenue_row.value_usd)

            if prior_revenue != 0:
                yoy_growth = (
                    values["revenue"] / prior_revenue - 1
                ) * 100

                yoy_rows = [
                    sources["revenue"],
                    str(prior_revenue_row.row_id),
                ]

    add(
        "revenue_yoy_growth_pct",
        "Revenue growth, year over year",
        yoy_growth,
        yoy_rows,
        "%",
    )

    return results