### iss_08 · period_cutoff · PERIOD_CUTOFF

params: shift_days=3

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-HCZHSV | — | **Dr 1200 · 9 501 832.70** | ▲ add |
| ROW-TOE2AJ | — | **Cr 4000 · 9 501 832.70** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 296 080 053.30 | ✓ 315 483 492.13 | I01 |
| detect | ✓ 0 | ✓ 9 501 832.70 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
