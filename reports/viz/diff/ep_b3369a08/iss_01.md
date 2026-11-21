### iss_01 + iss_05 · duplicate_invoice · GROUP

iss_01: duplicate_invoice · DUPLICATE_INVOICE (m0007) · params: shift_days=1, shift_minutes=42 · копия счёта INV-OAFLER
iss_05: period_cutoff · PERIOD_CUTOFF (m0008) · params: shift_days=1

**invoices**

| поле | clean | после m0007 | после m0008 | → |
| --- | --- | --- | --- | --- |
| INV-C5FMMN · invoice_id | — | **INV-C5FMMN** | **INV-C5FMMN** | ▲ add |
| INV-C5FMMN · doc_id | — | **DOC-LNIY7Q** | **DOC-LNIY7Q** | ▲ add |
| INV-C5FMMN · issued_at | — | **2026-11-01T15:56+05:00** | **2026-11-01T15:56+05:00** | ▲ +1d 42m от источника |
| INV-C5FMMN · total | — | **6 957.25 USD (695725)** | **6 957.25 USD (695725)** | ▲ = источник |

**ledger**

| поле | clean | после m0007 | после m0008 | → |
| --- | --- | --- | --- | --- |
| ROW-7ZQ27V | — | **—** | **Dr 1200 · 3 274 225.55** | ▲ add |
| ROW-CCLSJ3 | — | **—** | **Cr 4000 · 3 274 225.55** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 287 440 712.36 | ✓ 299 620 725.43 | I01 |
| detect iss_01 | ✓ 0 | ✓ 6 957.25 KZT | = expected · I07 |
| detect iss_05 | ✓ 0 | ✓ 3 274 225.55 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
