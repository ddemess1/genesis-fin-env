### iss_06 + iss_03 · fx_conversion · GROUP

iss_06: payment_allocation · PARTIAL_ALLOCATION (m0005) · params: allocated_share_pct=32
iss_03: fx_conversion · WRONG_FX_DATE (m0006) · params: variant=next_day+2:2026-11-02, wrong_rate=444.718285

**ledger**

| поле | clean | после m0005 | после m0006 | → |
| --- | --- | --- | --- | --- |
| ROW-2XMC6G | — | **Cr 2900 · 3 393 143.06** | **Cr 2900 · 3 393 143.06** | ▲ add |
| ROW-CZWPMS · credit_minor | 4 989 910.23 | **1 596 767.17** | **1 596 767.17** | ▲ modify |
| ROW-55LJF6 | — | **—** | **Dr 7900 · 8 482.86** | ▲ add |
| ROW-S4IFB6 · debit_minor | 4 989 910.23 | **4 989 910.23** | **4 981 427.37** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 296 080 053.30 | ✓ 315 483 492.13 | I01 |
| detect iss_06 | ✓ 0 | ✓ 7 616.90 KZT | = expected · I07 |
| detect iss_03 | ✓ 0 | ✓ 8 482.86 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
