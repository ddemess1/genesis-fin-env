### iss_03 + iss_02 · fx_conversion · GROUP

iss_03: payment_allocation · PARTIAL_ALLOCATION (m0002) · params: allocated_share_pct=51
iss_02: fx_conversion · WRONG_FX_DATE (m0003) · params: variant=next_day+2:2026-11-02, wrong_rate=1610.097888

**ledger**

| поле | clean | после m0002 | после m0003 | → |
| --- | --- | --- | --- | --- |
| ROW-DXIDMJ · credit_minor | 3 764 756.77 | **1 920 024.79** | **1 920 024.79** | ▲ modify |
| ROW-FUYEVC | — | **Cr 2900 · 1 844 731.98** | **Cr 2900 · 1 844 731.98** | ▲ add |
| ROW-5IIQKO · debit_minor | 3 764 756.77 | **3 764 756.77** | **3 756 474.30** | ▲ modify |
| ROW-SGG3L3 | — | **—** | **Dr 7900 · 8 282.47** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 197 079 004.14 | ✓ 197 202 364.28 | I01 |
| detect iss_03 | ✓ 0 | ✓ 11 432.06 KZT | = expected · I07 |
| detect iss_02 | ✓ 0 | ✓ 8 282.47 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
