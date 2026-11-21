### iss_01 · duplicate_invoice · DUPLICATE_INVOICE

params: shift_days=2, shift_minutes=187 · копия счёта INV-5P7SHJ

**invoices**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| INV-NNZGZ5 · invoice_id | — | **INV-NNZGZ5** | ▲ add |
| INV-NNZGZ5 · doc_id | — | **DOC-PBJAXU** | ▲ add |
| INV-NNZGZ5 · issued_at | — | **2026-10-24T11:41+05:00** | ▲ +2d 187m от источника |
| INV-NNZGZ5 · total | — | **1 871.78 USD (187178)** | ▲ = источник |

**ledger**

| поле | clean | dirty | → |
| --- | --- | --- | --- |
| ROW-BPKVEC | — | **Dr 1200 · 913 647.52** | ▲ add |
| ROW-PSIMQS | — | **Cr 4000 · 913 647.52** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 194 465 522.37 | ✓ 196 615 337.92 | I01 |
| detect | ✓ 0 | ✓ 1 871.78 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
