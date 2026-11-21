### iss_01 + iss_07 · duplicate_invoice · GROUP

iss_01: duplicate_invoice · DUPLICATE_INVOICE (m0009) · params: shift_days=3, shift_minutes=97 · копия счёта INV-JAXJ5T
iss_07: period_cutoff · PERIOD_CUTOFF (m0010) · params: shift_days=2

**invoices**

| поле | clean | после m0009 | после m0010 | → |
| --- | --- | --- | --- | --- |
| INV-FKGVFS · invoice_id | — | **INV-FKGVFS** | **INV-FKGVFS** | ▲ add |
| INV-FKGVFS · doc_id | — | **DOC-5HSXTG** | **DOC-5HSXTG** | ▲ add |
| INV-FKGVFS · issued_at | — | **2026-11-01T11:11+05:00** | **2026-11-01T11:11+05:00** | ▲ +3d 97m от источника |
| INV-FKGVFS · total | — | **9 623.13 USD (962313)** | **9 623.13 USD (962313)** | ▲ = источник |

**ledger**

| поле | clean | после m0009 | после m0010 | → |
| --- | --- | --- | --- | --- |
| ROW-GZPIOA | — | **—** | **Dr 1200 · 4 286 869.55** | ▲ add |
| ROW-K5BDUG | — | **—** | **Cr 4000 · 4 286 869.55** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 296 080 053.30 | ✓ 315 483 492.13 | I01 |
| detect iss_01 | ✓ 0 | ✓ 9 623.13 KZT | = expected · I07 |
| detect iss_07 | ✓ 0 | ✓ 4 286 869.55 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
