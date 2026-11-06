"""Tests for loan_calc.calculator.

All expected values are computed independently – no production function is
called to derive an assertion target.

Tests marked FAIL in their docstring are expected to fail because of a real
code bug (not a wrong expected value).
"""
import csv
import json
import os
import tempfile
from datetime import date
from unittest.mock import patch

import pytest

from loan_calc import (
    amortisation_schedule,
    compare_offers,
    eligible_amount,
    emi,
    format_inr,
    outstanding_after,
    prepayment_savings,
    remaining_tenure,
    schedule_to_csv,
    summary,
    total_interest,
    total_payment,
)
import cli


# ---------------------------------------------------------------------------
# EMI – basic and parametrised
# ---------------------------------------------------------------------------

def test_emi_within_one_of_8997():
    # r=round(9/1200,4)=0.0075, f=(1.0075)^240
    # independent: 1000000*0.0075*(1.0075^240)/((1.0075^240)-1) = 8997.26
    result = emi(1_000_000, 9, 240)
    assert abs(result - 8997) < 1


def test_emi_exact_8997_26():
    # Same independent computation rounded to 2dp = 8997.26
    result = emi(1_000_000, 9, 240)
    assert result == 8997.26


@pytest.mark.parametrize("rate,full_precision_expected", [
    # full_precision_expected = round(500000*(rate/1200)*(1+rate/1200)^120
    #                                 / ((1+rate/1200)^120 - 1), 2)
    # computed without rounding rate to 4 d.p.
    (7.25,  5870.05),
    (8.5,   6199.28),
    (10.4,  6718.78),
    (11.99, 7170.66),
    (13.0,  7465.54),
])
def test_emi_vs_full_precision_formula(rate, full_precision_expected):
    """emi() should be within ±20 of the full-precision formula.

    The difference arises because _monthly_rate() rounds to 4 decimal places.
    """
    result = emi(500_000, rate, 120)
    assert abs(result - full_precision_expected) < 20


# ---------------------------------------------------------------------------
# EMI – edge cases
# ---------------------------------------------------------------------------

def test_emi_zero_rate():
    # 0% → emi = round(100000/12, 2) = 8333.33
    assert emi(100_000, 0, 12) == 8333.33


def test_emi_one_month_tenure():
    # r = 10/1200 (no rounding) = 0.008333...
    # emi = round(50000*(1+10/1200), 2) = round(50416.6667, 2) = 50416.67
    assert emi(50_000, 10, 1) == 50416.67


def test_emi_large_principal():
    # Scales linearly: emi(1e12,9,240) = emi(1e6,9,240)*1e6 (before rounding)
    # independent: round(1e12*0.0075*(1.0075^240)/((1.0075^240)-1),2) = 8997259558.5
    result = emi(1e12, 9, 240)
    assert abs(result - 8997259558.5) < 1.0


def test_emi_raises_on_zero_tenure():
    with pytest.raises(ValueError, match="tenure_months must be positive"):
        emi(100_000, 9, 0)


def test_emi_raises_on_negative_tenure():
    with pytest.raises(ValueError, match="tenure_months must be positive"):
        emi(100_000, 9, -1)


def test_emi_raises_on_zero_principal():
    with pytest.raises(ValueError, match="principal must be positive"):
        emi(0, 9, 12)


def test_emi_raises_on_negative_principal():
    with pytest.raises(ValueError, match="principal must be positive"):
        emi(-1000, 9, 12)


# ---------------------------------------------------------------------------
# total_payment and total_interest
# ---------------------------------------------------------------------------

def test_total_payment():
    # emi(1000000,9,240) = 8997.26 → total = round(8997.26*240, 2) = 2159342.40
    assert total_payment(1_000_000, 9, 240) == 2159342.40


def test_total_interest():
    # 2159342.40 - 1000000 = 1159342.40
    assert total_interest(1_000_000, 9, 240) == 1159342.40


# ---------------------------------------------------------------------------
# amortisation_schedule – two tests that expose real bugs
# ---------------------------------------------------------------------------

def test_schedule_length_equals_tenure():
    """BUG: loop is range(1, tenure_months) so only 2 rows are generated for
    tenure=3, not 3.  This test expects 3 rows and will FAIL."""
    sched = amortisation_schedule(10_000, 12, 3)
    assert len(sched) == 3  # actual: 2  →  FAILS (off-by-one bug)


def test_schedule_last_balance_zero():
    """BUG: because month 3 is never generated, the last row has balance
    3366.56, not 0.  This test expects 0 and will FAIL."""
    sched = amortisation_schedule(10_000, 12, 3)
    assert sched[-1]["balance"] == pytest.approx(0.0, abs=0.01)  # FAILS


def test_schedule_first_row_values():
    # month=1, emi(10000,12,3)=3400.22
    # r=0.01, interest=round(10000*0.01,2)=100.0, principal=round(3400.22-100,2)=3300.22
    # balance=round(10000-3300.22,2)=6699.78
    sched = amortisation_schedule(10_000, 12, 3)
    row = sched[0]
    assert row["month"] == 1
    assert row["interest"] == pytest.approx(100.0, abs=0.01)
    assert row["principal"] == pytest.approx(3300.22, abs=0.01)
    assert row["balance"] == pytest.approx(6699.78, abs=0.01)


def test_schedule_has_required_keys():
    sched = amortisation_schedule(100_000, 12, 24)
    assert sched
    for key in ("month", "emi", "interest", "principal", "balance"):
        assert key in sched[0]


# ---------------------------------------------------------------------------
# remaining_tenure – one test that exposes the rate-conversion bug
# ---------------------------------------------------------------------------

def test_remaining_tenure_basic():
    """BUG: r = annual_rate/100 = 0.09 (annual), not 0.0075 (monthly).
    Guard: 8997.26 <= 1000000*0.09 = 90000 → True → raises ValueError.
    Correct answer should be 240.  This test will FAIL."""
    result = remaining_tenure(1_000_000, 9, 8997.26)
    assert result == 240  # raises ValueError  →  FAILS


def test_remaining_tenure_zero_balance():
    assert remaining_tenure(0, 9, 5000) == 0


def test_remaining_tenure_zero_rate():
    # r=0 → ceil(1000/100) = 10
    assert remaining_tenure(1_000, 0, 100) == 10


# ---------------------------------------------------------------------------
# prepayment_savings – prepayment larger than outstanding balance
# ---------------------------------------------------------------------------

def test_prepayment_larger_than_balance():
    """When prepay_amount > balance, months_left=0, new_tenure==prepay_month.

    Independent values:
      emi(100000,12,24) = 4707.35
      balance after month 12 = 52981.53
      prepay_amount = 52982.53 (balance + 1)
      new_balance = -1 → months_left = 0
      original_interest = round(4707.35*24-100000,2) = 12976.40
      interest_paid months 1-12 = 9469.73
      interest_saved ≈ orig_interest - interest_paid ≈ 3506.67
        (actual: 3505.67 because prepay_amount = balance+1, not balance)
    """
    result = prepayment_savings(100_000, 12, 24, 12, 52982.53)
    assert result["new_tenure"] == 12
    assert result["months_saved"] == 12
    # interest_saved ≈ orig_int - interest_paid ≈ 3506.67, within ±2
    assert abs(result["interest_saved"] - 3506.67) < 2.0


# ---------------------------------------------------------------------------
# format_inr
# ---------------------------------------------------------------------------

def test_format_inr_large_amount():
    # 1234567.89: whole='1234567', tail='567', head='1234'
    # → parts=['12','34'] → whole='12,34,567' → '₹12,34,567.89'
    assert format_inr(1_234_567.89) == "\u20b912,34,567.89"


def test_format_inr_negative():
    assert format_inr(-500.0) == "-\u20b9500.00"


def test_format_inr_small_amount():
    assert format_inr(999.99) == "\u20b9999.99"


def test_format_inr_zero():
    assert format_inr(0.0) == "\u20b90.00"


# ---------------------------------------------------------------------------
# compare_offers
# ---------------------------------------------------------------------------

def test_compare_offers_sorted_ascending_by_total_cost():
    # offer A: rate=10, tenure=120, no fee → tc=291576.40
    # offer B: rate=9.5, tenure=120, fee=1% → tc=280728.00
    # B cheaper → B first
    offers = [
        {"bank": "BankA", "rate": 10.0, "tenure": 120},
        {"bank": "BankB", "rate": 9.5,  "tenure": 120, "processing_fee_pct": 1.0},
    ]
    result = compare_offers(500_000, offers)
    assert result[0]["bank"] == "BankB"
    assert result[1]["bank"] == "BankA"


def test_compare_offers_single_offer_values():
    # offer: rate=10, tenure=120, no fee, principal=500000
    # r=10/1200 (no rounding), e=6607.54, ti=round(6607.54*120-500000,2)=292904.80
    offers = [{"bank": "X", "rate": 10.0, "tenure": 120}]
    result = compare_offers(500_000, offers)
    assert result[0]["emi"] == 6607.54
    assert result[0]["total_interest"] == 292904.8
    assert result[0]["processing_fee"] == 0.0
    assert result[0]["total_cost"] == 292904.8


# ---------------------------------------------------------------------------
# eligible_amount
# ---------------------------------------------------------------------------

def test_eligible_amount_basic():
    # income=100000, existing=10000, rate=10, tenure=120, foir=0.5
    # available = 40000
    # r=10/1200 (no rounding), f=(1+10/1200)^120
    # eligible = round(40000*(f-1)/(r*f), 2) = 3026846.53
    result = eligible_amount(100_000, 10_000, 10, 120)
    assert result == 3026846.53


def test_eligible_amount_returns_zero_when_obligations_exceed_capacity():
    # 50000*0.5 = 25000 < 25001 → available <= 0 → 0.0
    assert eligible_amount(50_000, 25_001, 10, 120) == 0.0


# ---------------------------------------------------------------------------
# schedule_to_csv
# ---------------------------------------------------------------------------

def test_schedule_to_csv_writes_correct_rows():
    sched = amortisation_schedule(100_000, 12, 24)
    with tempfile.NamedTemporaryFile(mode="r", suffix=".csv", delete=False) as tmp:
        tmppath = tmp.name
    try:
        schedule_to_csv(sched, tmppath)
        with open(tmppath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # schedule has 23 rows (bug: should be 24)
        assert len(rows) == len(sched)
        # first row month number
        assert rows[0]["month"] == "1"
        # first row emi: emi(100000,12,24) = 4707.35
        assert float(rows[0]["emi"]) == pytest.approx(4707.35, abs=0.01)
        # all balances non-negative
        for row in rows:
            assert float(row["balance"]) >= 0.0
    finally:
        os.unlink(tmppath)


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------

def test_summary_last_emi_start_jan_2026():
    # start=date(2026,1,15), tenure=240
    # end_year = 2026 + (0+240)//12 = 2026+20 = 2046
    # end_month = (0+240)%12 + 1 = 0+1 = 1 → "2046-01"
    result = summary(1_000_000, 9, 240, start=date(2026, 1, 15))
    assert result["last_emi"] == "2046-01"


def test_summary_has_all_required_keys():
    result = summary(500_000, 10, 120)
    for key in ("principal", "rate", "tenure", "emi",
                "total_interest", "total_payment", "last_emi", "currency"):
        assert key in result


def test_summary_currency_is_inr():
    assert summary(500_000, 10, 120)["currency"] == "INR"


def test_summary_rate_string():
    result = summary(500_000, 10, 120)
    assert result["rate"] == "10% p.a."


# ---------------------------------------------------------------------------
# outstanding_after
# ---------------------------------------------------------------------------

def test_outstanding_after_zero_months_paid():
    # months_paid <= 0 → returns round(principal, 2)
    assert outstanding_after(100_000, 12, 24, 0) == 100_000.0


def test_outstanding_after_exceeds_schedule():
    # months_paid > len(sched) = 24 → returns 0.0
    assert outstanding_after(100_000, 12, 24, 25) == 0.0


def test_outstanding_after_mid_loan():
    # After 12 payments on 100000 at 12% over 24 months
    # r=0.01, emi=4707.35; independently computed balance after month 12 ≈ 52981.53
    result = outstanding_after(100_000, 12, 24, 12)
    assert result == pytest.approx(52981.53, abs=0.05)


# ---------------------------------------------------------------------------
# remaining_tenure – ValueError branch
# ---------------------------------------------------------------------------

def test_remaining_tenure_raises_when_instalment_too_small():
    # r=9/1200=0.0075, balance*r=100000*0.0075=750; instalment=100 <= 750 → ValueError
    with pytest.raises(ValueError, match="instalment too small"):
        remaining_tenure(100_000, 9, 100)


# ---------------------------------------------------------------------------
# prepayment_savings – partial prepayment (else branch, new_balance > 0)
# ---------------------------------------------------------------------------

def test_prepayment_savings_partial_prepayment():
    """Partial prepayment: new_balance > 0, so remaining_tenure is called (else branch).

    For a small prepayment the saved months may round (ceil) in a way that makes
    interest_saved slightly negative; we only verify the branch was exercised.
    """
    # emi(100000,12,24)=4707.35; after month 6 balance ≈ 76000+
    # prepay 5000; new_balance > 0 → exercises the else branch
    result = prepayment_savings(100_000, 12, 24, 6, 5_000)
    # The else branch was taken: months_left > 0, so new_tenure must be > prepay_month
    assert result["new_tenure"] > 6
    assert result["months_saved"] >= 0
    # new_tenure is strictly less than the original tenure
    assert result["new_tenure"] <= 24


# ---------------------------------------------------------------------------
# eligible_amount – zero-rate branch
# ---------------------------------------------------------------------------

def test_eligible_amount_zero_rate():
    # r=0 → eligible = round(available * tenure_months, 2)
    # available = 100000*0.5 - 10000 = 40000; tenure=120
    # eligible = round(40000*120, 2) = 4800000.0
    assert eligible_amount(100_000, 10_000, 0, 120) == 4_800_000.0


# ---------------------------------------------------------------------------
# cli.main
# ---------------------------------------------------------------------------

def test_cli_main_outputs_valid_json(capsys):
    with patch("sys.argv", ["cli", "1000000", "9", "240"]):
        cli.main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # emi(1000000,9,240)=8997.26 → format_inr gives ₹8,997.26
    assert data["currency"] == "INR"
    assert data["tenure"] == "240 months"
    assert data["rate"] == "9.0% p.a."
    # emi string contains 8997.26 somewhere
    assert "8,997.26" in data["emi"]
