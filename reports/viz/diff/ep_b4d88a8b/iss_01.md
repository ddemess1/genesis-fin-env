### iss_01 · fx_conversion · WRONG_FX_RATE

params: variant=pct-12, wrong_rate=3.199694

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-WVUWST · debit_minor | 4 044 126.05 | **3 963 243.38** | ▲ modify |
| ROW-YXNFYF | — | **Dr 7900 · 80 882.67** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 201 319 615.21 | ✓ 208 668 865.00 | I01 |
| detect | ✓ 0 | ✓ 80 882.67 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
