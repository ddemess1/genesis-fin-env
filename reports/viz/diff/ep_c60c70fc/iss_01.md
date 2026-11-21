### iss_01 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=2, shift_minutes=28 · копия счёта INV-MQIOGD

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-R7KEGQ · invoice_id | — | **INV-R7KEGQ** | ▲ add |
| INV-R7KEGQ · doc_id | — | **DOC-RT63BD** | ▲ add |
| INV-R7KEGQ · issued_at | — | **2026-10-15T15:58+05:00** | ▲ +2d 28m от источника |
| INV-R7KEGQ · total | — | **74.174 KWD (74174)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-G4YGJL | — | **Cr 4000 · 123 360.14** | ▲ add |
| ROW-IP2GTH | — | **Dr 1200 · 123 360.14** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 197 079 004.14 | ✓ 197 202 364.28 | I01 |
| detect | ✓ 0 | ✓ 741.74 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
