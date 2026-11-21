### iss_06 · period_cutoff · PERIOD_CUTOFF

params: shift_days=1

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-4DXQNC | — | **Cr 4000 · 2 689 152.56** | ▲ add |
| ROW-V22OLE | — | **Dr 1200 · 2 689 152.56** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 287 440 712.36 | ✓ 299 620 725.43 | I01 |
| detect | ✓ 0 | ✓ 2 689 152.56 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
