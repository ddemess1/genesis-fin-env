### iss_02 · fx_conversion · WRONG_FX_RATE

params: variant=pct-15, wrong_rate=0.887790

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-7RWVNX | — | **Dr 7900 · 233.23** | ▲ add |
| ROW-B3IL3L · debit_minor | 4 664.56 | **4 431.33** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 362 760.11 | ✓ 362 760.11 | I01 |
| detect | ✓ 0 | ✓ 233.23 EUR | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
