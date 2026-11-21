### iss_02 · fx_conversion · WRONG_FX_DATE

params: variant=previous_day:2026-10-27, wrong_rate=465.904314

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-77AR5D | — | **Dr 7900 · 10 016.94** | ▲ add |
| ROW-P7SLAE · debit_minor | 2 339 538.51 | **2 329 521.57** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 201 319 615.21 | ✓ 208 668 865.00 | I01 |
| detect | ✓ 0 | ✓ 10 016.94 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
