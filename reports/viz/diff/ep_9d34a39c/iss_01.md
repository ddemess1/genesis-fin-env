### iss_01 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=1, shift_minutes=533 · копия счёта INV-46IGK6

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-RKQN2G · invoice_id | — | **INV-RKQN2G** | ▲ add |
| INV-RKQN2G · doc_id | — | **DOC-3ZSOSE** | ▲ add |
| INV-RKQN2G · issued_at | — | **2026-10-10T03:19-05:00** | ▲ +1d 533m от источника |
| INV-RKQN2G · total | — | **11 380.62 USD (1138062)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-A7Z4VW | — | **Cr 4000 · 11 380.62** | ▲ add |
| ROW-TJPHUT | — | **Dr 1200 · 11 380.62** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 382 900.41 | ✓ 411 686.86 | I01 |
| detect | ✓ 0 | ✓ 11 380.62 USD | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
