### iss_01 · fx_conversion · WRONG_FX_DATE

params: variant=invoice_date:2026-10-26, wrong_rate=512.975138

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-CIOEOW · debit_minor | 1 377 977.62 | **1 385 032.87** | ▲ modify |
| ROW-EVBNVT | — | **Cr 7900 · 7 055.25** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 204 723 083.38 | ✓ 210 799 639.31 | I01 |
| detect | ✓ 0 | ✓ 7 055.25 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
