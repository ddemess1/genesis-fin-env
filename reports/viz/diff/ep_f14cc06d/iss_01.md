### iss_01 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=0, shift_minutes=408 · копия счёта INV-5LNF4A

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-3SSV4W · invoice_id | — | **INV-3SSV4W** | ▲ add |
| INV-3SSV4W · doc_id | — | **DOC-HKJ7IB** | ▲ add |
| INV-3SSV4W · issued_at | — | **2026-10-02T21:29+05:00** | ▲ +0d 408m от источника |
| INV-3SSV4W · total | — | **2 453.46 USD (245346)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-6AMG6F | — | **Cr 4000 · 1 175 196.13** | ▲ add |
| ROW-LF7EZ3 | — | **Dr 1200 · 1 175 196.13** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 215 455 780.12 | ✓ 223 473 213.53 | I01 |
| detect | ✓ 0 | ✓ 2 453.46 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
