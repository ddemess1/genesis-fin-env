### iss_04 + iss_02 · fx_conversion · GROUP

iss_04: payment_allocation · PARTIAL_ALLOCATION (m0005) · params: allocated_share_pct=35
iss_02: fx_conversion · WRONG_FX_DATE (m0006) · params: variant=next_day+2:2026-11-02, wrong_rate=526.242461

**ledger**

| поле | clean | после m0005 | после m0006 | → |
| --- | --- | --- | --- | --- |
| ROW-2Y5A3T | — | **Cr 2900 · 1 577 587.49** | **Cr 2900 · 1 577 587.49** | ▲ add |
| ROW-QOJD5A · credit_minor | 2 427 050.40 | **849 462.91** | **849 462.91** | ▲ modify |
| ROW-6WLWV4 | — | **—** | **Cr 7900 · 4 368.69** | ▲ add |
| ROW-GFUHDR · debit_minor | 2 427 050.40 | **2 427 050.40** | **2 431 419.09** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 287 440 712.36 | ✓ 299 620 725.43 | I01 |
| detect iss_04 | ✓ 0 | ✓ 3 003.23 KZT | = expected · I07 |
| detect iss_02 | ✓ 0 | ✓ 4 368.69 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
