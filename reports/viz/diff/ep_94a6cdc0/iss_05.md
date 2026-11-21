### iss_05 + iss_04 · fx_conversion · GROUP

iss_05: payment_allocation · MISSING_ALLOCATION (m0007) · params: allocated_share_pct=0
iss_04: fx_conversion · WRONG_FX_DATE (m0008) · params: variant=next_day+2:2026-11-02, wrong_rate=444.718285

**ledger**

| поле | clean | после m0007 | после m0008 | → |
| --- | --- | --- | --- | --- |
| ROW-WSE74M · account | 1200 | **2900** | **2900** | ▲ modify |
| ROW-2BMUCI | — | **—** | **Dr 7900 · 4 690.19** | ▲ add |
| ROW-2O2J55 · debit_minor | 2 758 932.81 | **2 758 932.81** | **2 754 242.62** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 296 080 053.30 | ✓ 315 483 492.13 | I01 |
| detect iss_05 | ✓ 0 | ✓ 6 193.23 KZT | = expected · I07 |
| detect iss_04 | ✓ 0 | ✓ 4 690.19 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
