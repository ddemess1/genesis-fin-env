### iss_02 · payment_allocation · MISSING_ALLOCATION

params: allocated_share_pct=0

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-5OPWYM · account | 1200 | **2900** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 196 454 578.98 | ✓ 206 464 728.13 | I01 |
| detect | ✓ 0 | ✓ 16 741.86 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
