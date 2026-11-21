### iss_02 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=2, shift_minutes=370 · копия счёта INV-XRVQEU

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-SBENPM · invoice_id | — | **INV-SBENPM** | ▲ add |
| INV-SBENPM · doc_id | — | **DOC-VFEBVN** | ▲ add |
| INV-SBENPM · issued_at | — | **2026-10-04T15:18+05:00** | ▲ +2d 370m от источника |
| INV-SBENPM · total | — | **1 467 800.00 KZT (146780000)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-26LDQB | — | **Cr 4000 · 1 467 800.00** | ▲ add |
| ROW-6VJKBB | — | **Dr 1200 · 1 467 800.00** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 215 455 780.12 | ✓ 223 473 213.53 | I01 |
| detect | ✓ 0 | ✓ 1 467 800.00 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
