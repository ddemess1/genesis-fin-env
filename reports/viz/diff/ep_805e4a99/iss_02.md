### iss_02 · payment_allocation · PARTIAL_ALLOCATION

params: allocated_share_pct=77

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-HNFOD2 | — | **Cr 2900 · 546 692.82** | ▲ add |
| ROW-VAGYAZ · credit_minor | 2 376 925.29 | **1 830 232.47** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 178 619 299.23 | ✓ 179 441 962.62 | I01 |
| detect | ✓ 0 | ✓ 546 692.82 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
