### iss_02 · fx_conversion · WRONG_FX_DATE

params: variant=previous_day:2026-10-14, wrong_rate=456.841362

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-5RDXCR · debit_minor | 3 337 515.70 | **3 355 298.79** | ▲ modify |
| ROW-CFZ6OH | — | **Cr 7900 · 17 783.09** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 296 080 053.30 | ✓ 315 483 492.13 | I01 |
| detect | ✓ 0 | ✓ 17 783.09 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
