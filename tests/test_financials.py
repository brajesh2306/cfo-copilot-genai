
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from services.financials import (
    canonical_item,
    to_usd,
    free_cash_flow,
    compute_kpis,
    source_values,
    get_engine,
)


def test_unit_normalization():
    assert to_usd(2, "USD_thousands") == 2000
    assert to_usd(2, "USD_millions") == 2_000_000
    assert to_usd(2, "USD") == 2


def test_known_aliases():
    assert canonical_item("Net sales") == "revenue"
    assert canonical_item("Total stockholders' equity") == "total_equity"
    assert canonical_item("Gross margin") == "gross_profit"
    assert canonical_item("Gross profit") == "gross_profit"
    assert canonical_item("mystery metric") is None


def test_fcf_uses_capex_as_positive_outflow():
    value, rows = free_cash_flow(
        {"cash_from_operations": 100, "capital_expenditures": 20},
        {"cash_from_operations": "a", "capital_expenditures": "b"},
    )
    assert value == 80
    assert rows == ["a", "b"]


def test_nwi_drop2_amended_filing_is_ingested():
    get_engine()
    rows = source_values("NWI", 2024, 3)

    amended = rows[rows["filing_id"] == "NWI-10QA-FY2024Q3"]

    assert not amended.empty
    assert "R900279" in amended["row_id"].values
    assert "R900277" in amended["row_id"].values


def test_nwi_amended_gross_margin():
    get_engine()
    kpis = compute_kpis("NWI", 2024, 3)

    gross_margin = next(
        k for k in kpis if k["kpi_id"] == "gross_margin_pct"
    )

    assert gross_margin["value"] is not None
    assert abs(gross_margin["value"] - 36.37784) < 0.01
    assert "R900279" in gross_margin["source_row_ids"]
    assert "R900277" in gross_margin["source_row_ids"]

def test_nwi_yoy_uses_amended_current_period_revenue():
    kpis = compute_kpis("NWI", 2024, 3)

    yoy = next(
        k for k in kpis
        if k["kpi_id"] == "revenue_yoy_growth_pct"
    )

    assert yoy["status"] == "available"
    assert abs(yoy["value"] - 4.2644404332) < 0.001

    # Current-period revenue must come from the amended filing.
    assert "R900277" in yoy["source_row_ids"]

    # Prior-year revenue must also be traceable.
    assert "R000145" in yoy["source_row_ids"]


def test_zlg_drop2_has_sixteen_kpis():
    kpis = compute_kpis("ZLG", 2024, 3)

    assert len(kpis) == 16

    yoy = next(
        k for k in kpis
        if k["kpi_id"] == "revenue_yoy_growth_pct"
    )

    assert yoy["status"] == "available"
    assert abs(yoy["value"] - 4.4622425629) < 0.001
    assert len(yoy["source_row_ids"]) == 2


def test_missing_company_period_does_not_invent_kpi_values():
    kpis = compute_kpis("NONEXISTENT", 2099, 1)

    assert len(kpis) == 16

    for kpi in kpis:
        assert kpi["value"] is None
        assert kpi["status"] == "missing_input"
        assert kpi["source_row_ids"] == []
        assert kpi["confidence"] == "low"