import math
from datetime import date

# --- EMI basic ---
r = round(9/1200, 4)  # 0.0075
f = (1+r)**240
emi_1m_9_240 = round(1000000*r*f/(f-1), 2)
print(f"emi(1000000,9,240) = {emi_1m_9_240}")

# --- EMI 0% ---
emi_0pct = round(100000/12, 2)
print(f"emi(100000,0,12) = {emi_0pct}")

# --- EMI 1-month ---
r1 = round(10/1200, 4)
f1 = (1+r1)**1
emi_1m = round(50000*r1*f1/(f1-1), 2)
print(f"emi(50000,10,1) = {emi_1m}")

# --- EMI large principal ---
r2 = round(9/1200, 4)
f2 = (1+r2)**240
emi_large = round(1e12*r2*f2/(f2-1), 2)
print(f"emi(1e12,9,240) = {emi_large}")

# --- Parametrised: code_emi vs full_emi, p=500000, n=120 ---
print("Parametrised (p=500000, n=120):")
for rate in [7.25, 8.5, 10.4, 11.99, 13.0]:
    rc = round(rate/1200, 4)
    fc = (1+rc)**120
    ec = round(500000*rc*fc/(fc-1), 2)
    rf = rate/1200
    ff = (1+rf)**120
    ef = round(500000*rf*ff/(ff-1), 2)
    print(f"  rate={rate}: r_code={rc}, code_emi={ec}, full_emi={ef}, diff={abs(ec-ef):.2f}")

# --- Schedule bug ---
# amortisation_schedule(100000, 12, 24) has range(1,24)=23 rows, not 24
# amortisation_schedule(10000, 12, 3) has range(1,3)=2 rows, last balance != 0
r3 = round(12/1200, 4)  # 0.01
f3 = (1+r3)**3
inst3 = round(10000*r3*f3/(f3-1), 2)
print(f"\nemi(10000,12,3) = {inst3}")
bal3 = 10000.0
for i in range(1, 3):
    interest = round(bal3*r3, 2)
    pp = round(inst3-interest, 2)
    bal3 = round(bal3-pp, 2)
print(f"balance after 2 rows (expected nonzero): {bal3}")

# --- remaining_tenure bug ---
# remaining_tenure(1000000, 9, 8997.26): r=9/100=0.09, guard: 8997.26 <= 1000000*0.09=90000 -> True -> raises ValueError
print(f"\nremaining_tenure guard: 8997.26 <= {1000000*(9/100)} = {8997.26 <= 1000000*(9/100)}")

# --- prepayment: prepay_amount just over balance ---
r4 = round(12/1200, 4)  # 0.01
f4 = (1+r4)**24
inst4 = round(100000*r4*f4/(f4-1), 2)
print(f"\nemi(100000,12,24) = {inst4}")
bal4 = 100000.0
interest_sum = 0.0
for i in range(1, 13):
    interest = round(bal4*r4, 2)
    pp = round(inst4-interest, 2)
    interest_sum += interest
    bal4 = round(bal4-pp, 2)
print(f"balance after month 12 = {bal4}")
print(f"interest_paid months 1-12 = {round(interest_sum, 2)}")
# prepay_amount = bal4 + 1 (just over)
prepay_amount = bal4 + 1.0
new_balance = bal4 - prepay_amount  # = -1
print(f"new_balance = {new_balance}")
# months_left = 0
# new_tenure = 12 + 0 = 12
# original_interest
orig_int4 = round(inst4*24 - 100000, 2)
print(f"original_interest(100000,12,24) = {orig_int4}")
# new_total = inst4*12 + prepay_amount + inst4*0
new_total = inst4*12 + prepay_amount
new_interest = new_total - 100000
interest_saved = round(orig_int4 - new_interest, 2)
print(f"interest_saved (prepay_month=12, prepay_amount=bal+1) = {interest_saved}")
# Should be approx orig_int4 - interest_sum
print(f"orig_int - interest_paid = {round(orig_int4 - round(interest_sum,2), 2)}")

# --- format_inr ---
# format_inr(1234567.89):
# whole='1234567', frac='89'
# head='1234', tail='567'
# iter: parts=['34'], head='12' -> len<=2, exit
# head='12' exists -> parts=['12','34']
# whole = '12,34,567', result = '₹12,34,567.89'
print(f"\nformat_inr(1234567.89) expected: ₹12,34,567.89")
print(f"format_inr(-500.00) expected: -₹500.00")
print(f"format_inr(999.99) expected: ₹999.99")

# --- compare_offers ---
p_co = 500000
r_a = round(10/1200, 4)
f_a = (1+r_a)**120
e_a = round(p_co*r_a*f_a/(f_a-1), 2)
ti_a = round(e_a*120 - p_co, 2)
tc_a = ti_a
print(f"\nofferA: emi={e_a}, ti={ti_a}, fee=0, tc={tc_a}")

r_b = round(9.5/1200, 4)
f_b = (1+r_b)**120
e_b = round(p_co*r_b*f_b/(f_b-1), 2)
ti_b = round(e_b*120 - p_co, 2)
fee_b = round(1.0*p_co/100, 2)
tc_b = round(ti_b + fee_b, 2)
print(f"offerB: emi={e_b}, ti={ti_b}, fee={fee_b}, tc={tc_b}")
print(f"cheaper (lower tc): {'B' if tc_b < tc_a else 'A'}, B_tc={tc_b}, A_tc={tc_a}")

# --- eligible_amount ---
r_e = round(10/1200, 4)
f_e = (1+r_e)**120
avail = 100000*0.5 - 10000  # 40000
elig = round(avail*(f_e-1)/(r_e*f_e), 2)
print(f"\neligible_amount(100000,10000,10,120) = {elig}")

# --- schedule_to_csv: schedule length ---
# amortisation_schedule(100000,12,24) has 23 rows
print(f"\namortisation_schedule(100000,12,24) length = 23 (not 24, bug)")

# --- summary last_emi ---
start = date(2026, 1, 15)
tenure_months_s = 240
end_year = start.year + (start.month - 1 + tenure_months_s) // 12
end_month = (start.month - 1 + tenure_months_s) % 12 + 1
print(f"\nsummary last_emi (start=2026-01-15, tenure=240): {end_year}-{end_month:02d}")
