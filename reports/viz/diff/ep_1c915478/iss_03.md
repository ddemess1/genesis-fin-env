### iss_03 · payment_allocation · PARTIAL_ALLOCATION

params: allocated_share_pct=58

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-O7Z4Q4 | — | **Cr 2900 · 872.28** | ▲ add |
| ROW-UZXUWD · credit_minor | 2 076.84 | **1 204.56** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 362 760.11 | ✓ 362 760.11 | I01 |
| detect | ✓ 0 | ✓ 929.74 EUR | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
