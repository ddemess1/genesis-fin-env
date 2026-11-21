### iss_01 · fx_conversion · WRONG_FX_RATE

params: variant=pct-14, wrong_rate=0.006072

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-PJJB7E · debit_minor | 6 919.88 | **6 642.04** | ▲ modify |
| ROW-VIOLT3 | — | **Dr 7900 · 277.84** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 362 760.11 | ✓ 362 760.11 | I01 |
| detect | ✓ 0 | ✓ 277.84 EUR | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
