### iss_01 + iss_03 · duplicate_invoice · GROUP

iss_01: duplicate_invoice · DUPLICATE_INVOICE (m0003) · params: shift_days=1, shift_minutes=98 · копия счёта INV-IPEBYO
iss_03: period_cutoff · PERIOD_CUTOFF (m0004) · params: shift_days=1

**invoices**

| поле | clean | после m0003 | после m0004 | → |
| --- | --- | --- | --- | --- |
| INV-EFUQ5V · invoice_id | — | **INV-EFUQ5V** | **INV-EFUQ5V** | ▲ add |
| INV-EFUQ5V · doc_id | — | **DOC-E4JDHQ** | **DOC-E4JDHQ** | ▲ add |
| INV-EFUQ5V · issued_at | — | **2026-11-01T15:30+05:00** | **2026-11-01T15:30+05:00** | ▲ +1d 98m от источника |
| INV-EFUQ5V · total | — | **17 674.06 USD (1767406)** | **17 674.06 USD (1767406)** | ▲ = источник |

**ledger**

| поле | clean | после m0003 | после m0004 | → |
| --- | --- | --- | --- | --- |
| ROW-BE2SM7 | — | **—** | **Cr 4000 · 8 490 867.50** | ▲ add |
| ROW-N7DPJD | — | **—** | **Dr 1200 · 8 490 867.50** | ▲ add |

**проверка**

| инвариант | clean | dirty | |
| --- | --- | --- | --- |
| ΣDr = ΣCr | ✓ 196 454 578.98 | ✓ 206 464 728.13 | I01 |
| detect iss_01 | ✓ 0 | ✓ 17 674.06 KZT | = expected · I07 |
| detect iss_03 | ✓ 0 | ✓ 8 490 867.50 KZT | = expected · I07 |
| вне diff |  | ✓ 0 изменений | I12 |
