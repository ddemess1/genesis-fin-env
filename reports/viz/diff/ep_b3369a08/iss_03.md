### iss_03 · fx_conversion · WRONG_FX_RATE

params: variant=pct13, wrong_rate=488.704758

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-4H2L4W | — | **Cr 7900 · 207 686.75** | ▲ add |
| ROW-XNMJE3 · debit_minor | 6 922 891.97 | **7 130 578.72** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 287 440 712.36 | ✓ 299 620 725.43 | I01 |
| detect | ✓ 0 | ✓ 207 686.75 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
