"""Custom exception hierarchy for loan_calc."""


class LoanCalcError(Exception):
    """Base exception for all loan_calc errors."""


class InvalidLoanInputError(LoanCalcError, ValueError):
    """Raised when a loan input parameter is invalid.

    Subclasses both :class:`LoanCalcError` and :class:`ValueError` so that
    callers that catch ``ValueError`` continue to work.
    """


class InvalidPrincipalError(InvalidLoanInputError):
    """Raised when ``principal`` is not a positive finite number."""


class InvalidRateError(InvalidLoanInputError):
    """Raised when ``annual_rate`` is not a finite number in [0, 100]."""


class InvalidTenureError(InvalidLoanInputError):
    """Raised when ``tenure_months`` is not a positive integer."""


class InvalidPrepaymentError(InvalidLoanInputError):
    """Raised when prepayment parameters (month or amount) are out of range."""


class UnrepayableLoanError(LoanCalcError, ValueError):
    """Raised when the fixed instalment cannot repay the loan.

    Subclasses both :class:`LoanCalcError` and :class:`ValueError` so that
    callers that catch ``ValueError`` continue to work.
    """
