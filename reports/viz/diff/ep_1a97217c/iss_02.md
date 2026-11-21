### iss_02 · payment_allocation · MISSING_ALLOCATION

params: allocated_share_pct=0

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-5AAYXB · account | 1200 | **2900** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 170 225 307.13 | ✓ 170 853 107.13 | I01 |
| detect | ✓ 0 | ✓ 4 251 600.00 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
