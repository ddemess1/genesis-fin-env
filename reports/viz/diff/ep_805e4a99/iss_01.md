### iss_01 · payment_allocation · PARTIAL_ALLOCATION

params: allocated_share_pct=32

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-FJJGHE | — | **Cr 2900 · 1 501 517.42** | ▲ add |
| ROW-JHBE2R · credit_minor | 2 208 113.85 | **706 596.43** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 178 619 299.23 | ✓ 179 441 962.62 | I01 |
| detect | ✓ 0 | ✓ 1 501 517.42 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
