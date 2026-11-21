### iss_01 · period_cutoff · PERIOD_CUTOFF

params: shift_days=3

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-MRY5GX | — | **Cr 4000 · 1 234 313.99** | ▲ add |
| ROW-WACWZM | — | **Dr 1200 · 1 234 313.99** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 158 548 243.95 | ✓ 160 576 850.89 | I01 |
| detect | ✓ 0 | ✓ 1 234 313.99 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
