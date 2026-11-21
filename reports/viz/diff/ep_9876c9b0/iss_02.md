### iss_02 · period_cutoff · PERIOD_CUTOFF

params: shift_days=2

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-TMSVCH | — | **Dr 1200 · 1 890 914.87** | ▲ add |
| ROW-X4VKXL | — | **Cr 4000 · 1 890 914.87** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 191 803 460.30 | ✓ 201 014 293.27 | I01 |
| detect | ✓ 0 | ✓ 1 890 914.87 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
