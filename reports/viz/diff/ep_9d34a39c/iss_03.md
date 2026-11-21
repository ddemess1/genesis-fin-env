### iss_02 + iss_03 · duplicate_invoice · GROUP

iss_02: duplicate_invoice · DUPLICATE_INVOICE (m0003) · params: shift_days=1, shift_minutes=70 · копия счёта INV-ZZSDPW
iss_03: period_cutoff · PERIOD_CUTOFF (m0004) · params: shift_days=2

**invoices**

| поле | clean | после m0003 | после m0004 | → |
| --- | --- | --- | --- | --- |
| INV-7P3IX6 · invoice_id | — | **INV-7P3IX6** | **INV-7P3IX6** | ▲ add |
| INV-7P3IX6 · doc_id | — | **DOC-UWGKOY** | **DOC-UWGKOY** | ▲ add |
| INV-7P3IX6 · issued_at | — | **2026-11-01T17:26-05:00** | **2026-11-01T17:26-05:00** | ▲ +1d 70m от источника |
| INV-7P3IX6 · total | — | **8 752.88 USD (875288)** | **8 752.88 USD (875288)** | ▲ = источник |

**ledger**

| поле | clean | после m0003 | после m0004 | → |
| --- | --- | --- | --- | --- |
| ROW-NUTBKS | — | **—** | **Dr 1200 · 8 752.88** | ▲ add |
| ROW-QJLISN | — | **—** | **Cr 4000 · 8 752.88** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 382 900.41 | ✓ 411 686.86 | I01 |
| detect iss_02 | ✓ 0 | ✓ 8 752.88 USD | = expected · I07 |
| detect iss_03 | ✓ 0 | ✓ 8 752.88 USD | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
