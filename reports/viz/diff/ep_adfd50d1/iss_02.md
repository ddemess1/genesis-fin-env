### iss_02 · payment_allocation · PARTIAL_ALLOCATION

params: allocated_share_pct=31

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-TTYDJ5 | — | **Cr 2900 · 2 252 446.54** | ▲ add |
| ROW-TYCIT2 · credit_minor | 3 264 415.27 | **1 011 968.73** | ▲ modify |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 202 035 824.99 | ✓ 203 728 964.70 | I01 |
| detect | ✓ 0 | ✓ 2 252 446.54 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
