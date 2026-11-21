### iss_02 · payment_allocation · MISSING_ALLOCATION

params: allocated_share_pct=0

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-OLRHKV · account | 1200 | **2900** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 204 723 083.38 | ✓ 210 799 639.31 | I01 |
| detect | ✓ 0 | ✓ 3 601.18 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
