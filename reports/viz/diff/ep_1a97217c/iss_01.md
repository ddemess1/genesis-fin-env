### iss_01 · payment_allocation · PARTIAL_ALLOCATION

params: allocated_share_pct=71

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-6PQFSH | — | **Cr 2900 · 611 584.94** | ▲ add |
| ROW-CHBAPB · credit_minor | 2 108 913.56 | **1 497 328.62** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 170 225 307.13 | ✓ 170 853 107.13 | I01 |
| detect | ✓ 0 | ✓ 611 584.94 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
