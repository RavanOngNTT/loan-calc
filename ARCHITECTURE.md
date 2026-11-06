# ARCHITECTURE.md

## What it is

`loan-calc` is a pure-Python library (and thin CLI wrapper) for common retail-loan arithmetic.
It has no external runtime dependencies.
Everything lives in `loan_calc/calculator.py`; `loan_calc/__init__.py` re-exports all calculator
functions and the full exception hierarchy. There is a `cli.py` at the repo root that is not part
of the library itself.

The library answers questions such as:
- What is my monthly EMI?
- How much interest will I pay in total?
- What does my repayment schedule look like month by month?
- How much can I borrow given my income?
- How much do I save if I make a lump-sum prepayment?
- Which bank offer is cheapest overall?

---

## Conventions

| Convention | Detail |
|---|---|
| Currency | `DEFAULT_CURRENCY = "INR"`. All monetary amounts are plain Python `float`. |
| Rates | Every public function accepts `annual_rate` as a **percentage** (e.g. `12` means 12 % p.a.). The helper `_monthly_rate` converts to a monthly decimal by dividing by 1200. |
| Rounding | Intermediate and final values are rounded with `round(..., 2)`. Each rounding step introduces up to ±0.005 error; these accumulate across a long schedule. |
| Return types | Scalar functions return `float`. Schedule functions return a list of dicts. `summary()` returns a dict of human-readable strings. |
| Formatting | `format_inr()` formats a float as an Indian-locale rupee string (e.g. `₹1,23,456.78`). |

---

## Functions

### `_monthly_rate(annual_rate) → float`
**Private helper.**
- Input: annual interest rate as a percentage (e.g. 12 for 12 %).
- Output: monthly rate as a decimal (no additional rounding).
- Formula: `annual_rate / 1200`.
- Example: `_monthly_rate(12)` → `0.01`.

---

### `emi(principal, annual_rate, tenure_months) → float`
- Inputs: loan amount, annual rate %, number of monthly instalments.
- Output: the fixed monthly instalment (EMI) as a float.
- Calls: `_validate_principal`, `_validate_rate`, `_validate_tenure`, `_monthly_rate`.
- Formula (standard reducing-balance EMI):
  ```
  r = monthly_rate
  f = (1 + r) ^ tenure_months
  EMI = principal * r * f / (f - 1)
  ```
  When r == 0 (zero-interest loan): `EMI = principal / tenure_months`.
- Raises `InvalidPrincipalError` if principal is not a positive finite number.
- Raises `InvalidRateError` if annual_rate is not in [0, 100] or is not finite.
- Raises `InvalidTenureError` if tenure_months is not a positive integer.
- Precision: one `round(...,2)` at the end.

---

### `total_payment(principal, annual_rate, tenure_months) → float`
- Output: `emi * tenure_months`, rounded to 2 decimal places.
- Calls: `emi`.

---

### `total_interest(principal, annual_rate, tenure_months) → float`
- Output: `total_payment - principal`, rounded to 2 decimal places.
- Calls: `total_payment`.

---

### `amortisation_schedule(principal, annual_rate, tenure_months) → list[dict]`
- Output: a list of exactly `tenure_months` row dicts, each with keys `month`, `emi`, `interest`, `principal`, `balance`. The final row always has `balance == 0.0`.
- Calls: `_monthly_rate`, `emi`.
- How it works: starts with `balance = principal`. For each month, computes `interest = balance * r`, `principal_part = emi - interest`, updates `balance`. On the final month, `principal_part` is set to the exact remaining balance so the loan closes cleanly.

**Row-by-row trace for `amortisation_schedule(30000, 12, 3)`** (verified against current code):

Setup:
- `r = _monthly_rate(12) = 12/1200 = 0.01`
- `instalment = emi(30000, 12, 3) = round(10200.6633…, 2) = 10200.66`
- `balance = 30000`
- Loop: `for month in range(1, 4)` → months 1, 2, 3

**Month 1:**
- `interest = round(30000 * 0.01, 2) = 300.00`
- `principal_part = round(10200.66 - 300.00, 2) = 9900.66`
- Not final month → `instalment_amt = 10200.66`
- `balance = round(30000 - 9900.66, 2) = 20099.34`
- Row: `{month:1, emi:10200.66, interest:300.00, principal:9900.66, balance:20099.34}`

**Month 2:**
- `interest = round(20099.34 * 0.01, 2) = 200.99`
- `principal_part = round(10200.66 - 200.99, 2) = 9999.67`
- Not final month → `instalment_amt = 10200.66`
- `balance = round(20099.34 - 9999.67, 2) = 10099.67`
- Row: `{month:2, emi:10200.66, interest:200.99, principal:9999.67, balance:10099.67}`

**Month 3 (final):**
- `interest = round(10099.67 * 0.01, 2) = 101.00`
- Final month → `principal_part = round(10099.67, 2) = 10099.67`, `instalment_amt = round(10099.67 + 101.00, 2) = 10200.67`
- `balance = round(10099.67 - 10099.67, 2) = 0.0`
- Row: `{month:3, emi:10200.67, interest:101.00, principal:10099.67, balance:0.0}`

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid) → float`
- Output: the remaining balance after `months_paid` payments.
- Calls: `amortisation_schedule`.
- Returns `round(principal, 2)` if `months_paid <= 0`; `0.0` if `months_paid > len(schedule)`.

---

### `remaining_tenure(balance, annual_rate, instalment) → int`
- Output: number of months needed to repay `balance` at the given fixed `instalment`.
- Calls: `_validate_rate`.
- Derivation of the formula used:

  Starting from the EMI equation:
  ```
  EMI = P * r * (1+r)^n / ((1+r)^n - 1)
  ```
  Rearrange to isolate `(1+r)^n`:
  ```
  (1+r)^n = EMI / (EMI - P*r)
  n = -log(1 - P*r/EMI) / log(1+r)
  ```
  The code returns `math.ceil(n)`, where `r = annual_rate / 1200` (monthly rate).

- Raises `UnrepayableLoanError` if `instalment <= balance * r`.

---

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount) → dict`
- Output: dict with keys `emi`, `months_saved`, `new_tenure`, `interest_saved`, `interest_paid_before_prepayment`.
- Calls: `emi`, `amortisation_schedule`, `remaining_tenure`, `total_interest`.
- Validation: `prepay_month` must be in `[1, tenure_months]`; `prepay_amount` must be non-negative finite.
- When `prepay_amount >= balance`, the effective prepayment is capped at `balance` so that excess payment is not counted as interest.
- `interest_saved = original_interest - new_interest`, where `new_interest = new_total_paid - principal`.

---

### `compare_offers(principal, offers) → list[dict]`
- Input: `offers` is a list of dicts, each with keys `bank`, `rate`, `tenure`, and optional `processing_fee_pct`.
- Output: list of dicts sorted by `total_cost` (total interest + processing fee), ascending.
- Calls: `emi`, `total_interest`.

---

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5) → float`
- Output: maximum loan amount a borrower can be offered.
- FOIR (Fixed Obligation to Income Ratio) caps total EMI outflow at `foir * monthly_income`.
- Available EMI = `monthly_income * foir - existing_emis`.
- Uses the inverse of the EMI formula to back out the principal.
- Calls: `_validate_rate`, `_validate_tenure`, `_monthly_rate`.

---

### `format_inr(amount) → str`
- Input: a float.
- Output: Indian-locale rupee string, e.g. `₹12,34,567.89` or `-₹500.00`.
- No external calls; pure string manipulation.

---

### `schedule_to_csv(rows, path)`
- Writes the list of dicts from `amortisation_schedule` to a CSV file at `path`.
- No return value.

---

### `summary(principal, annual_rate, tenure_months, start=None) → dict`
- Output: a human-readable summary dict with keys `principal`, `rate`, `tenure`, `emi`, `total_interest`, `total_payment`, `last_emi`, `currency`.
- Calls: `emi`, `total_interest`, `total_payment`, `format_inr`.
- **`start` argument:** the loan disbursement date (i.e. the date from which the first EMI period
  begins). It defaults to `date.today()`. It is used only to compute the `last_emi` field, which
  is formatted as `"YYYY-MM"` and represents the calendar month in which the final EMI falls.
  - Formula: `end_year = start.year + (start.month - 1 + tenure_months) // 12`; `end_month = (start.month - 1 + tenure_months) % 12 + 1`.
  - Example: `start = date(2026, 1, 15)`, `tenure_months = 240` → `last_emi = "2046-01"`. *(Verified: `python -c "from datetime import date; from loan_calc import summary; print(summary(1000000,9,240,start=date(2026,1,15))['last_emi'])"` → `2046-01`.)*
  - Note: `start = date(2026, 1, 1)` with `tenure_months = 3` → `last_emi = "2026-04"` (not `"2026-03"` as originally documented — see Bugs found and fixed below).

---

## Errors

The library defines a custom exception hierarchy in `loan_calc/exceptions.py`. All exceptions are
exported from `loan_calc/__init__.py`.

```
Exception
└── LoanCalcError                   # base for all loan_calc errors
    ├── InvalidLoanInputError       # also subclasses ValueError
    │   ├── InvalidPrincipalError   # principal not a positive finite number
    │   ├── InvalidRateError        # rate not in [0, 100] or not finite
    │   ├── InvalidTenureError      # tenure not a positive integer
    │   └── InvalidPrepaymentError  # prepay_month out of range or prepay_amount negative/NaN
    └── UnrepayableLoanError        # also subclasses ValueError; instalment too small to repay
```

**Key design decisions:**
- `InvalidLoanInputError` and `UnrepayableLoanError` both subclass `ValueError` so that existing
  code that catches `ValueError` continues to work.
- `emi()` validates all three of its arguments before computing anything; since `amortisation_schedule`,
  `total_payment`, `total_interest`, and `summary` all call `emi`, they inherit validation for free.
- `remaining_tenure()` validates `annual_rate` and raises `UnrepayableLoanError` (not bare `ValueError`)
  when the instalment is too small.
- `prepayment_savings()` validates `prepay_month` (must be an int in `[1, tenure_months]`) and
  `prepay_amount` (must be a non-negative finite number) before delegating to `emi`.
- `eligible_amount()` validates `annual_rate` and `tenure_months` directly.

**What is rejected:**
- NaN or infinity for any numeric argument
- Python `bool` values (e.g. `True`/`False`) for numeric arguments
- Non-numeric types (e.g. strings) for numeric arguments
- `annual_rate` outside `[0, 100]`
- `tenure_months` that is not a plain positive `int`
- `prepay_month` outside `[1, tenure_months]`
- Negative `prepay_amount`

---

## Bugs found and fixed

### Bug 1 — `_monthly_rate` rounded to 4 decimal places
**What it was:** `r = round(annual_rate / 1200, 4)` — for rates like 8.5 %, the monthly rate
(0.007083…) was truncated to 0.0071, an error of ~0.00008/month that compounded to a ~12 rupee
EMI error over 120 months.

**Fix:** Removed the `round(…, 4)` call. Now `r = annual_rate / 1200` with full float precision.

**Impact:** `emi(1000000, 8.5, 240)` changed from 8690.89 to the correct 8678.23.

---

### Bug 2 — `amortisation_schedule` loop was off by one
**What it was:** `for month in range(1, tenure_months)` — the loop stopped at `tenure_months - 1`,
so the final month row was never appended. The `if month == tenure_months:` branch inside the loop
was dead code that could never execute. The schedule was always one row short, and the last
recorded balance was not zero.

**Fix:** Changed to `range(1, tenure_months + 1)`. The dead branch now executes for the final
month: it sets `principal_part = balance` (clearing the exact remaining amount) and computes the
adjusted final instalment.

**Impact:** `amortisation_schedule(30000, 12, 3)` now returns 3 rows (was 2) and the last row
has `balance == 0.0`.

---

### Bug 3 — `remaining_tenure` used annual rate where monthly rate is required
**What it was:** `r = annual_rate / 100` — this gave the annual decimal (e.g. 9 % → 0.09). The
tenure formula requires the monthly rate (0.0075). With the annual rate, the guard
`instalment <= balance * r` triggered for every realistic EMI (e.g. 8997.26 ≤ 90 000), so
`remaining_tenure` always raised `ValueError` for any normal loan.

**Fix:** Changed `annual_rate / 100` to `annual_rate / 1200`.

**Impact:** `remaining_tenure(1000000, 9, 8997.26)` now returns 240 (previously always raised).

---

### Bug 4 — `prepayment_savings` overcounted interest when prepayment exceeded the balance
**What it was:** When `prepay_amount > balance`, the formula used the full `prepay_amount` in
`new_total`, counting the excess (the amount beyond what was owed) as interest paid. This made
`interest_saved` strongly negative for large overpayments.

**Fix:** When `new_balance <= 0` (prepayment clears the loan), the effective prepayment is capped
at the actual outstanding `balance`. Excess payment is returned to the borrower and is not interest.

**Impact:** `prepayment_savings(1000000, 9, 240, 24, 5000000)` now gives
`interest_saved = 982619.11 = original_interest − interest_paid_before_prepayment`
(previously gave -3056591.84).

---

### Documentation error — `summary` start example
**What it was:** ARCHITECTURE.md originally stated that `start = date(2026, 1, 1)` with
`tenure_months = 3` gives `last_emi = "2026-03"`.

**What is actually true:** The formula is
`end_month = (start.month - 1 + tenure_months) % 12 + 1 = (0 + 3) % 12 + 1 = 4`,
so `last_emi = "2026-04"`. The example was off by one month.

**Verified:** `python -c "from datetime import date; from loan_calc import summary; print(summary(1000000,9,3,start=date(2026,1,1))['last_emi'])"` → `2026-04`.
