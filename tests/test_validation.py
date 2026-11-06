"""Tests for input validation and the LoanCalcError exception hierarchy.

All tests verify that invalid inputs raise the correct exception subclass
and that the exception hierarchy is correct.
"""
import math

import pytest

import loan_calc as lc
from loan_calc import (
    eligible_amount,
    emi,
    prepayment_savings,
    remaining_tenure,
)
from loan_calc.exceptions import (
    InvalidLoanInputError,
    InvalidPrepaymentError,
    InvalidPrincipalError,
    InvalidRateError,
    InvalidTenureError,
    LoanCalcError,
    UnrepayableLoanError,
)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

def test_loan_calc_error_is_exception():
    assert issubclass(LoanCalcError, Exception)


def test_invalid_loan_input_error_subclasses():
    assert issubclass(InvalidLoanInputError, LoanCalcError)
    assert issubclass(InvalidLoanInputError, ValueError)


def test_invalid_principal_error_subclasses():
    assert issubclass(InvalidPrincipalError, InvalidLoanInputError)
    assert issubclass(InvalidPrincipalError, ValueError)


def test_invalid_rate_error_subclasses():
    assert issubclass(InvalidRateError, InvalidLoanInputError)
    assert issubclass(InvalidRateError, ValueError)


def test_invalid_tenure_error_subclasses():
    assert issubclass(InvalidTenureError, InvalidLoanInputError)
    assert issubclass(InvalidTenureError, ValueError)


def test_invalid_prepayment_error_subclasses():
    assert issubclass(InvalidPrepaymentError, InvalidLoanInputError)
    assert issubclass(InvalidPrepaymentError, ValueError)


def test_unrepayable_loan_error_subclasses():
    assert issubclass(UnrepayableLoanError, LoanCalcError)
    assert issubclass(UnrepayableLoanError, ValueError)


def test_exported_from_package():
    # All exception classes are accessible from the top-level package
    assert issubclass(lc.InvalidRateError, ValueError)
    assert issubclass(lc.UnrepayableLoanError, lc.LoanCalcError)


# ---------------------------------------------------------------------------
# InvalidPrincipalError
# ---------------------------------------------------------------------------

def test_emi_raises_on_zero_principal_custom():
    with pytest.raises(InvalidPrincipalError):
        emi(0, 9, 12)


def test_emi_raises_on_negative_principal():
    with pytest.raises(InvalidPrincipalError):
        emi(-1000, 9, 12)


def test_emi_raises_on_nan_principal():
    with pytest.raises(InvalidPrincipalError):
        emi(math.nan, 9, 12)


def test_emi_raises_on_inf_principal():
    with pytest.raises(InvalidPrincipalError):
        emi(math.inf, 9, 12)


def test_emi_raises_on_bool_principal():
    with pytest.raises(InvalidPrincipalError):
        emi(True, 9, 12)


def test_emi_raises_on_string_principal():
    with pytest.raises(InvalidPrincipalError):
        emi("100000", 9, 12)


# ---------------------------------------------------------------------------
# InvalidRateError
# ---------------------------------------------------------------------------

def test_emi_raises_on_negative_rate():
    with pytest.raises(InvalidRateError):
        emi(100_000, -1, 12)


def test_emi_raises_on_rate_above_100():
    with pytest.raises(InvalidRateError):
        emi(100_000, 101, 12)


def test_emi_raises_on_nan_rate():
    with pytest.raises(InvalidRateError):
        emi(100_000, math.nan, 12)


def test_emi_raises_on_inf_rate():
    with pytest.raises(InvalidRateError):
        emi(100_000, math.inf, 12)


def test_emi_raises_on_bool_rate():
    with pytest.raises(InvalidRateError):
        emi(100_000, True, 12)


def test_emi_raises_on_string_rate():
    with pytest.raises(InvalidRateError):
        emi(100_000, "9", 12)


def test_emi_rate_zero_is_valid():
    # 0% is a valid rate
    result = emi(100_000, 0, 12)
    assert result == 8333.33


def test_emi_rate_100_is_valid():
    # Exactly 100% is accepted (boundary)
    result = emi(100_000, 100, 12)
    assert result > 0


# ---------------------------------------------------------------------------
# InvalidTenureError
# ---------------------------------------------------------------------------

def test_emi_raises_on_zero_tenure_custom():
    with pytest.raises(InvalidTenureError):
        emi(100_000, 9, 0)


def test_emi_raises_on_negative_tenure():
    with pytest.raises(InvalidTenureError):
        emi(100_000, 9, -1)


def test_emi_raises_on_float_tenure():
    # Non-integer tenure must be rejected
    with pytest.raises(InvalidTenureError):
        emi(100_000, 9, 3.5)


def test_emi_raises_on_bool_tenure():
    with pytest.raises(InvalidTenureError):
        emi(100_000, 9, True)


def test_emi_raises_on_string_tenure():
    with pytest.raises(InvalidTenureError):
        emi(100_000, 9, "12")


# ---------------------------------------------------------------------------
# UnrepayableLoanError
# ---------------------------------------------------------------------------

def test_remaining_tenure_raises_unrepayable():
    # r=9/1200=0.0075; balance*r=100000*0.0075=750; instalment=100 <= 750
    with pytest.raises(UnrepayableLoanError):
        remaining_tenure(100_000, 9, 100)


def test_unrepayable_is_also_value_error():
    # Must be catchable as ValueError for backward compatibility
    with pytest.raises(ValueError):
        remaining_tenure(100_000, 9, 100)


# ---------------------------------------------------------------------------
# InvalidPrepaymentError
# ---------------------------------------------------------------------------

def test_prepayment_raises_on_month_zero():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, 0, 5_000)


def test_prepayment_raises_on_month_beyond_tenure():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, 25, 5_000)


def test_prepayment_raises_on_negative_amount():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, 6, -1_000)


def test_prepayment_raises_on_nan_amount():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, 6, math.nan)


def test_prepayment_raises_on_bool_month():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, True, 5_000)


def test_prepayment_raises_on_string_amount():
    with pytest.raises(InvalidPrepaymentError):
        prepayment_savings(100_000, 12, 24, 6, "5000")


# ---------------------------------------------------------------------------
# eligible_amount validation (rate and tenure)
# ---------------------------------------------------------------------------

def test_eligible_raises_on_invalid_rate():
    with pytest.raises(InvalidRateError):
        eligible_amount(100_000, 10_000, -5, 120)


def test_eligible_raises_on_float_tenure():
    with pytest.raises(InvalidTenureError):
        eligible_amount(100_000, 10_000, 10, 12.5)


# ---------------------------------------------------------------------------
# Custom exceptions are catchable as ValueError (backward compatibility)
# ---------------------------------------------------------------------------

def test_invalid_principal_is_value_error():
    with pytest.raises(ValueError):
        emi(0, 9, 12)


def test_invalid_rate_is_value_error():
    with pytest.raises(ValueError):
        emi(100_000, 150, 12)


def test_invalid_tenure_is_value_error():
    with pytest.raises(ValueError):
        emi(100_000, 9, 0)
