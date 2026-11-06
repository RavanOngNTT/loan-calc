# ARCHITECTURE.md

## What it is

`loan-calc` is a pure-Python library (and thin CLI wrapper) for common retail-loan arithmetic.
It has no external runtime dependencies.
Everything lives in `loan_calc/calculator.py`; `loan_calc/__init__.py` re-exports everything with `from .calculator import *`.
There is a `cli.py` at the repo root that is not part of the library itself.

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
- Output: monthly rate as a decimal, rounded to 4 decimal places.
- Formula: `round(annual_rate / 1200, 4)`.
- Example: `_monthly_rate(12)` → `0.01`.
- Precision note: rounding to 4 decimal places loses any sub-0.00005-per-month precision. For very low rates this is noticeable.

---

### `emi(principal, annual_rate, tenure_months) → float`
- Inputs: loan amount, annual rate %, number of monthly instalments.
- Output: the fixed monthly instalment (EMI) as a float.
- Calls: `_monthly_rate`.
- Formula (standard reducing-balance EMI):
  ```
  r = monthly_rate
  f = (1 + r) ^ tenure_months
  EMI = principal * r * f / (f - 1)
  ```
  When r == 0 (zero-interest loan): `EMI = principal / tenure_months`.
- Raises `ValueError` if `tenure_months <= 0` or `principal <= 0`.
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
- Output: a list of row dicts, each with keys `month`, `emi`, `interest`, `principal`, `balance`.
- Calls: `_monthly_rate`, `emi`.
- How it works: starts with `balance = principal`. For each month, computes `interest = balance * r`, `principal_part = emi - interest`, updates `balance`.

**Row-by-row trace for `amortisation_schedule(30000, 12, 3)`:**

Setup:
- `r = _monthly_rate(12) = round(12/1200, 4) = 0.01`
- `instalment = emi(30000, 12, 3)`
  - `f = (1.01)^3 = 1.030301`
  - `= round(30000 * 0.01 * 1.030301 / 0.030301, 2)`
  - `= round(309.0903 / 0.030301, 2)`
  - `= round(10200.6718…, 2) = 10200.67`
- `balance = 30000`
- Loop: `for month in range(1, 3)` → months **1 and 2 only** (see bug below)

**Month 1:**
- `interest = round(30000 * 0.01, 2) = 300.00`
- `principal_part = round(10200.67 - 300.00, 2) = 9900.67`
- `month == tenure_months`? 1 == 3? **No** → `instalment_amt = 10200.67`
- `balance = round(30000 - 9900.67, 2) = 20099.33`
- Row: `{month:1, emi:10200.67, interest:300.00, principal:9900.67, balance:20099.33}`

**Month 2:**
- `interest = round(20099.33 * 0.01, 2) = round(200.9933, 2) = 200.99`
- `principal_part = round(10200.67 - 200.99, 2) = 9999.68`
- `month == tenure_months`? 2 == 3? **No** → `instalment_amt = 10200.67`
- `balance = round(20099.33 - 9999.68, 2) = 10099.65`
- Row: `{month:2, emi:10200.67, interest:200.99, principal:9999.68, balance:10099.65}`

**Month 3: never generated.** `range(1, 3)` stops before 3.

Final returned list has **2 rows**, not 3. The balance after month 2 is 10099.65, not 0.

---

### `outstanding_after(principal, annual_rate, tenure_months, months_paid) → float`
- Output: the remaining balance after `months_paid` payments.
- Calls: `amortisation_schedule`.
- Returns `principal` if `months_paid <= 0`; `0.0` if `months_paid > len(schedule)`.
- Because `amortisation_schedule` only generates `tenure_months - 1` rows, `outstanding_after` with `months_paid == tenure_months` returns `0.0` (from the guard) rather than the true final balance.

---

### `remaining_tenure(balance, annual_rate, instalment) → int`
- Output: number of months needed to repay `balance` at the given fixed `instalment`.
- Derivation of the formula used:

  Starting from the EMI equation:
  ```
  EMI = P * r * (1+r)^n / ((1+r)^n - 1)
  ```
  Rearrange to isolate `(1+r)^n`:
  ```
  EMI * ((1+r)^n - 1) = P * r * (1+r)^n
  (1+r)^n * (EMI - P*r) = EMI
  (1+r)^n = EMI / (EMI - P*r)
  n = log(EMI / (EMI - P*r)) / log(1+r)
     = -log(1 - P*r/EMI) / log(1+r)
  ```
  The code returns `math.ceil(n)`.

**Rate-conversion bug:** the code does `r = annual_rate / 100`, which gives the annual rate as a decimal (e.g. 12 % → 0.12). The formula above requires the **monthly** rate. The correct conversion is `annual_rate / 1200` (e.g. 12 % → 0.01). Using the annual rate makes `balance * r` twelve times too large, the guard `instalment <= balance * r` triggers far too early, and when it does not trigger the computed tenure is wildly wrong.

---

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount) → dict`
- Output: dict with keys `emi`, `months_saved`, `new_tenure`, `interest_saved`, `interest_paid_before_prepayment`.
- Calls: `emi`, `amortisation_schedule`, `remaining_tenure`, `total_interest`.
- Logic: take the balance after `prepay_month`, subtract the lump sum, compute new tenure using `remaining_tenure`, compare interest totals.
- Inherits the `remaining_tenure` rate bug and the `amortisation_schedule` off-by-one.

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
- Calls: `_monthly_rate`.

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
- **`start` argument:** the loan disbursement date (i.e. the date the first EMI period begins). It defaults to `date.today()`. It is used only to compute the `last_emi` field, which is formatted as `"YYYY-MM"` and represents the calendar month in which the final EMI falls. Example: if `start = date(2026, 1, 1)` and `tenure_months = 3`, then `last_emi = "2026-03"`.

---

## Things that look wrong

### 1. `amortisation_schedule` loop is off by one — the last month is never generated

```python
for month in range(1, tenure_months):   # stops at tenure_months - 1
```

Should be `range(1, tenure_months + 1)`. The dead code inside:

```python
if month == tenure_months:   # never True inside this loop
    principal_part = round(balance, 2)
    instalment_amt = round(principal_part + interest, 2)
```

…was intended to handle the last month's rounding, but because the loop never reaches `tenure_months`, this branch is unreachable. As a consequence:
- The returned schedule is always one row short.
- The final balance in the last row is not zero (it equals roughly one month's outstanding principal).
- `outstanding_after` and `prepayment_savings` inherit this error.

---

### 2. `remaining_tenure` uses annual rate where monthly rate is required

```python
r = annual_rate / 100   # gives annual decimal, e.g. 0.12 for 12 %
```

Should be:

```python
r = annual_rate / 1200  # gives monthly decimal, e.g. 0.01 for 12 %
```

The standard tenure formula requires the same periodicity as the instalment (monthly). Using an annual rate produces a tenure that is not meaningful.

---

### 3. `_monthly_rate` truncates precision at 4 decimal places

For unusual rates (e.g. 8.75 % → monthly = 0.007291…) rounding to 4 places gives 0.0073, an error of ~0.0001/month. Over a 20-year mortgage this compounds into a visible discrepancy in total interest.

---

### 4. No input validation on most functions

Only `emi` validates its inputs. Functions like `amortisation_schedule`, `eligible_amount`, and `outstanding_after` accept zero, negative, or nonsensical values without raising errors.
