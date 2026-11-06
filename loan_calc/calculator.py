import math
from datetime import date
from typing import Optional


DEFAULT_CURRENCY = "INR"


def _monthly_rate(annual_rate: float) -> float:
    r = annual_rate / 1200
    return r


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the fixed monthly instalment (EMI) for a reducing-balance loan.

    Uses the standard annuity formula. The monthly rate is derived from
    ``annual_rate`` via :func:`_monthly_rate` (rounded to 4 decimal places).
    When the rate is zero the instalment is simply ``principal / tenure_months``.

    Args:
        principal: Loan amount in the currency of the caller. Must be > 0.
        annual_rate: Annual interest rate as a percentage (e.g. ``12`` for 12 %).
        tenure_months: Total number of monthly instalments. Must be > 0.

    Returns:
        The fixed monthly EMI rounded to 2 decimal places.

    Raises:
        ValueError: If ``tenure_months <= 0`` or ``principal <= 0``.
    """
    if tenure_months <= 0:
        raise ValueError("tenure must be positive")
    if principal <= 0:
        raise ValueError("principal must be positive")
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(principal / tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(principal * r * f / (f - 1), 2)


def total_payment(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the total amount paid over the full loan term.

    Computed as ``emi * tenure_months`` and rounded to 2 decimal places.

    Args:
        principal: Loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Total number of monthly instalments. Must be > 0.

    Returns:
        Total repayment amount rounded to 2 decimal places.

    Raises:
        ValueError: Propagated from :func:`emi` if inputs are invalid.
    """
    return round(emi(principal, annual_rate, tenure_months) * tenure_months, 2)


def total_interest(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the total interest paid over the full loan term.

    Computed as ``total_payment - principal`` and rounded to 2 decimal places.

    Args:
        principal: Loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Total number of monthly instalments. Must be > 0.

    Returns:
        Total interest paid rounded to 2 decimal places.

    Raises:
        ValueError: Propagated from :func:`emi` if inputs are invalid.
    """
    return round(total_payment(principal, annual_rate, tenure_months) - principal, 2)


def amortisation_schedule(
    principal: float, annual_rate: float, tenure_months: int
) -> list[dict]:
    """Generate a month-by-month repayment schedule.

    Each row dict has the keys:

    * ``month`` – 1-based month number.
    * ``emi`` – instalment paid that month. For all months except the last
      this equals the standard EMI; the final month's instalment is adjusted
      to clear the exact remaining balance.
    * ``interest`` – interest component for that month, rounded to 2 d.p.
    * ``principal`` – principal component for that month, rounded to 2 d.p.
    * ``balance`` – outstanding principal after that payment (floored at 0).

    Args:
        principal: Loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Total number of instalments. Must be > 0.

    Returns:
        List of exactly ``tenure_months`` row dicts. The final row has
        ``balance == 0.0``.

    Raises:
        ValueError: Propagated from :func:`emi` if inputs are invalid.
    """
    r = _monthly_rate(annual_rate)
    instalment = emi(principal, annual_rate, tenure_months)
    balance = principal
    rows = []
    for month in range(1, tenure_months + 1):
        interest = round(balance * r, 2)
        principal_part = round(instalment - interest, 2)
        if month == tenure_months:
            principal_part = round(balance, 2)
            instalment_amt = round(principal_part + interest, 2)
        else:
            instalment_amt = instalment
        balance = round(balance - principal_part, 2)
        rows.append({
            "month": month,
            "emi": instalment_amt,
            "interest": interest,
            "principal": principal_part,
            "balance": max(balance, 0.0),
        })
    return rows


def outstanding_after(
    principal: float, annual_rate: float, tenure_months: int, months_paid: int
) -> float:
    """Return the outstanding loan balance after a given number of payments.

    Looks up the balance from :func:`amortisation_schedule`.

    Args:
        principal: Original loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Total intended number of instalments. Must be > 0.
        months_paid: Number of instalments already made.

    Returns:
        Outstanding balance rounded to 2 decimal places, or ``0.0`` if
        ``months_paid`` exceeds the length of the generated schedule.
    """
    if months_paid <= 0:
        return round(principal, 2)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    if months_paid > len(sched):
        return 0.0
    return sched[months_paid - 1]["balance"]


def remaining_tenure(balance: float, annual_rate: float, instalment: float) -> int:
    """Estimate the number of monthly payments needed to clear a balance.

    Uses the closed-form rearrangement of the EMI formula::

        n = -log(1 - balance * r / instalment) / log(1 + r)

    where ``r`` is the monthly rate (``annual_rate / 1200``).

    Args:
        balance: Outstanding principal to be repaid.
        annual_rate: Annual interest rate as a percentage.
        instalment: Fixed monthly payment amount.

    Returns:
        Ceiling of the computed number of monthly periods needed.

    Raises:
        ValueError: If ``instalment <= balance * r``, i.e. the instalment is
            too small to cover the first month's interest.
    """
    r = annual_rate / 1200
    if balance <= 0:
        return 0
    if r == 0:
        return math.ceil(balance / instalment)
    if instalment <= balance * r:
        raise ValueError("instalment too small to repay the loan")
    n = -math.log(1 - balance * r / instalment) / math.log(1 + r)
    return math.ceil(n)


def prepayment_savings(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepay_month: int,
    prepay_amount: float,
) -> dict:
    """Estimate interest savings from a lump-sum prepayment while keeping the same EMI.

    After the prepayment the remaining balance is reduced by ``prepay_amount``
    and the new tenure is estimated via :func:`remaining_tenure`. Both
    :func:`amortisation_schedule` (off-by-one on the last row) and
    :func:`remaining_tenure` (uses annual rate instead of monthly rate)
    propagate their known inaccuracies into the result.

    Args:
        principal: Original loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Original total number of monthly instalments. Must be > 0.
        prepay_month: The month number after which the lump sum is paid (1-based).
        prepay_amount: Lump-sum prepayment amount.

    Returns:
        A dict with keys:

        * ``emi`` – the original fixed instalment.
        * ``months_saved`` – reduction in tenure compared with the original.
        * ``new_tenure`` – total months from start under the new schedule.
        * ``interest_saved`` – difference in total interest paid, rounded to 2 d.p.
        * ``interest_paid_before_prepayment`` – cumulative interest up to
          ``prepay_month``, rounded to 2 d.p.
    """
    instalment = emi(principal, annual_rate, tenure_months)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    balance = sched[prepay_month - 1]["balance"]
    new_balance = balance - prepay_amount
    if new_balance <= 0:
        months_left = 0
        effective_prepay = balance  # cap at actual outstanding; excess is not interest
    else:
        months_left = remaining_tenure(new_balance, annual_rate, instalment)
        effective_prepay = prepay_amount
    original_left = tenure_months - prepay_month
    interest_paid_so_far = sum(row["interest"] for row in sched[:prepay_month])
    original_interest = total_interest(principal, annual_rate, tenure_months)
    new_total = instalment * prepay_month + effective_prepay + instalment * months_left
    new_interest = new_total - principal
    return {
        "emi": instalment,
        "months_saved": original_left - months_left,
        "new_tenure": prepay_month + months_left,
        "interest_saved": round(original_interest - new_interest, 2),
        "interest_paid_before_prepayment": round(interest_paid_so_far, 2),
    }


def compare_offers(principal: float, offers: list[dict]) -> list[dict]:
    """Compare multiple loan offers and rank them by total cost.

    Total cost for each offer is ``total_interest + processing_fee``.

    Args:
        principal: Loan amount to be compared across offers.
        offers: List of offer dicts. Each dict must contain:

            * ``bank`` (str) – lender name.
            * ``rate`` (float) – annual interest rate as a percentage.
            * ``tenure`` (int) – repayment tenure in months.
            * ``processing_fee_pct`` (float, optional) – processing fee as a
              percentage of ``principal``; defaults to ``0`` if absent.

    Returns:
        List of result dicts sorted by ``total_cost`` ascending. Each dict
        contains ``bank``, ``emi``, ``total_interest``, ``processing_fee``,
        and ``total_cost``, all rounded to 2 decimal places.
    """
    out = []
    for o in offers:
        e = emi(principal, o["rate"], o["tenure"])
        ti = total_interest(principal, o["rate"], o["tenure"])
        fee = o.get("processing_fee_pct", 0) * principal / 100
        out.append({
            "bank": o["bank"],
            "emi": e,
            "total_interest": ti,
            "processing_fee": round(fee, 2),
            "total_cost": round(ti + fee, 2),
        })
    out.sort(key=lambda x: x["total_cost"])
    return out


def eligible_amount(
    monthly_income: float,
    existing_emis: float,
    annual_rate: float,
    tenure_months: int,
    foir: float = 0.5,
) -> float:
    """Estimate the maximum loan amount a borrower is eligible for.

    Uses the Fixed Obligation to Income Ratio (FOIR) approach: the available
    monthly EMI capacity is ``monthly_income * foir - existing_emis``. That
    capacity is then back-solved through the EMI formula to derive the
    corresponding principal.

    Args:
        monthly_income: Gross monthly income of the borrower.
        existing_emis: Total existing monthly EMI obligations.
        annual_rate: Annual interest rate as a percentage for the new loan.
        tenure_months: Proposed loan tenure in months.
        foir: Maximum fraction of monthly income allowed for all EMIs combined.
            Defaults to ``0.5`` (50 %).

    Returns:
        Maximum eligible loan amount rounded to 2 decimal places, or ``0.0``
        if ``monthly_income * foir <= existing_emis``.
    """
    available = monthly_income * foir - existing_emis
    if available <= 0:
        return 0.0
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(available * tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(available * (f - 1) / (r * f), 2)


def format_inr(amount: float) -> str:
    """Format a float as an Indian-locale rupee string.

    Uses the Indian numbering system where groups of two digits follow the
    initial group of three (e.g. ``1,23,456.78``).

    Args:
        amount: Monetary value to format. Negative values are prefixed with
            a minus sign.

    Returns:
        A string of the form ``"₹1,23,456.78"`` or ``"-₹500.00"``.
    """
    neg = amount < 0
    amount = abs(round(amount, 2))
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + frac


def schedule_to_csv(rows: list[dict], path: str) -> None:
    """Write an amortisation schedule to a CSV file.

    The file will have a header row followed by one data row per month.
    Columns: ``month``, ``emi``, ``interest``, ``principal``, ``balance``.

    Args:
        rows: List of row dicts as returned by :func:`amortisation_schedule`.
        path: File-system path where the CSV will be written (created or
            overwritten).

    Returns:
        None
    """
    with open(path, "w") as fh:
        fh.write("month,emi,interest,principal,balance\n")
        for r in rows:
            fh.write(f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n')


def summary(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    start: Optional[date] = None,
) -> dict:
    """Produce a human-readable summary of a loan.

    Args:
        principal: Loan amount. Must be > 0.
        annual_rate: Annual interest rate as a percentage.
        tenure_months: Total number of monthly instalments. Must be > 0.
        start: Loan disbursement date (the date from which the first EMI
            period begins). Used only to compute ``last_emi``. Defaults to
            ``date.today()``.

    Returns:
        A dict with string values for keys: ``principal``, ``rate``,
        ``tenure``, ``emi``, ``total_interest``, ``total_payment``,
        ``last_emi`` (formatted as ``"YYYY-MM"``), and ``currency``.

    Raises:
        ValueError: Propagated from :func:`emi` if inputs are invalid.
    """
    start = start or date.today()
    e = emi(principal, annual_rate, tenure_months)
    end_year = start.year + (start.month - 1 + tenure_months) // 12
    end_month = (start.month - 1 + tenure_months) % 12 + 1
    return {
        "principal": format_inr(principal),
        "rate": f"{annual_rate}% p.a.",
        "tenure": f"{tenure_months} months",
        "emi": format_inr(e),
        "total_interest": format_inr(total_interest(principal, annual_rate, tenure_months)),
        "total_payment": format_inr(total_payment(principal, annual_rate, tenure_months)),
        "last_emi": f"{end_year}-{end_month:02d}",
        "currency": DEFAULT_CURRENCY,
    }
