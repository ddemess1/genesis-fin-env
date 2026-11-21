### iss_02 + iss_01 · fx_conversion · GROUP

iss_02: payment_allocation · MISSING_ALLOCATION (m0002) · params: allocated_share_pct=0
iss_01: fx_conversion · WRONG_FX_DATE (m0003) · params: variant=next_day+2:2026-11-02, wrong_rate=492.534190

**ledger**

| поле | clean | после m0002 | после m0003 | → |
| --- | --- | --- | --- | --- |
| ROW-6EIFIW · account | 1200 | **2900** | **2900** | ▲ modify |
| ROW-LSUZN4 | — | **—** | **Cr 7900 · 3 177.05** | ▲ add |
| ROW-PBCQSU · debit_minor | 1 765 025.62 | **1 765 025.62** | **1 768 202.67** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 174 827 471.19 | ✓ 180 694 042.11 | I01 |
| detect iss_02 | ✓ 0 | ✓ 3 590.01 KZT | = expected · I07 |
| detect iss_01 | ✓ 0 | ✓ 3 177.05 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
