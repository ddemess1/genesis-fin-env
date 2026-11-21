### iss_01 · period_cutoff · PERIOD_CUTOFF

params: shift_days=2

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-GD5INL | — | **Cr 4000 · 4 662 536.15** | ▲ add |
| ROW-PTZRHV | — | **Dr 1200 · 4 662 536.15** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 191 803 460.30 | ✓ 201 014 293.27 | I01 |
| detect | ✓ 0 | ✓ 4 662 536.15 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
