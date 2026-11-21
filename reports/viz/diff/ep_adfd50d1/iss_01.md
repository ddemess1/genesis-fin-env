### iss_01 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=3, shift_minutes=463 · копия счёта INV-532HLU

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-7TEYHP · invoice_id | — | **INV-7TEYHP** | ▲ add |
| INV-7TEYHP · doc_id | — | **DOC-JT5N56** | ▲ add |
| INV-7TEYHP · issued_at | — | **2026-07-10T02:09+06:00** | ▲ +3d 463m от источника |
| INV-7TEYHP · total | — | **2 034.17 USD (203417)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-5YZCXS | — | **Dr 1200 · 940 363.84** | ▲ add |
| ROW-X7WGY6 | — | **Cr 4000 · 940 363.84** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 202 035 824.99 | ✓ 203 728 964.70 | I01 |
| detect | ✓ 0 | ✓ 2 034.17 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
