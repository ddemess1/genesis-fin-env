# Self-audit (ожидаемая оценка по нашей трактовке критериев жюри)

- код: `5a8eedf431a0` · конфиги: `fb32cb874aa2` · suite `v1` · python 3.13 · зависимости: `b4ed6e5689e8`
- время прогона: 17 с

| Блок | Пройдено | Баллы |
| --- | --- | --- |
| Контракт и изоляция | 20/20 | 25.0 / 25 |
| Данные и эталон | 20/20 | 25.0 / 25 |
| Надёжность награды | 20/20 | 25.0 / 25 |
| Воспроизводимость | 20/20 | 15.0 / 15 |
| **Авто-итог** | | **90.0 / 90** |

Блокирующие нарушения: нет. Ещё 10 баллов (инженерия) ставит человек.

## Проверки

| ID | Блок | Что проверяем | Итог | мс | Детали |
| --- | --- | --- | --- | --- | --- |
| C01 | contract | reset returns JSON-serialisable (obs, info) | ✓ | 19 | obs and info dumped with json.dumps |
| C02 | contract | first observation: task, manifest, policy, steps_left=100; no seed/truth | ✓ | 11 | keys=['manifest', 'policy', 'steps_left', 'task'] leaks=[] |
| C03 | contract | manifest counts equal table lengths | ✓ | 10 | manifest={'documents': 69, 'fx': 70, 'invoices': 42, 'ledger': 256, 'payments': 27} paged={'ledger': 256, 'invoices': 42, 'payments': 27, 'fx': 70} |
| C04 | contract | page limit: limit=51 is BAD_ARGS (step spent), limit=50 returns <= 50 rows | ✓ | 8 | rule documented in README: limit > 50 -> BAD_ARGS, never silent truncation |
| C05 | contract | cursor traversal returns every row once, in file order | ✓ | 12 | 4 tables, no gaps, no repeats |
| C06 | contract | same cursor twice gives an identical page (also in a fresh reset) | ✓ | 17 | cursor is an opaque HMAC token of (table, offset) |
| C07 | contract | get_record returns the row from the file | ✓ | 13 | 8 records compared |
| C08 | contract | get_document returns the jsonl row | ✓ | 13 | 10 documents compared |
| C09 | contract | calculator: 0.1+0.2 = 0.3 (decimal arithmetic) | ✓ | 7 | 0.1+0.2=0.3 |
| C10 | contract | calculator rejects code, files and huge powers; the step is spent | ✓ | 8 | 7 rejected |
| C11 | contract | unknown id -> UNKNOWN_ID, step spent | ✓ | 8 | 5 lookups |
| C12 | contract | unknown action -> BAD_ACTION, step spent | ✓ | 9 | 6 malformed actions |
| C13 | contract | wrong argument types -> BAD_ARGS, step spent | ✓ | 9 | 8 bad calls |
| C14 | contract | 200 random junk actions: no exception, no traceback or path in any observation | ✓ | 12 | no crash |
| C15 | contract | submit ends the episode (terminated=True); later steps are EPISODE_DONE | ✓ | 9 | terminated, then EPISODE_DONE |
| C16 | contract | submit on step 100 (after 99 inspections) is accepted | ✓ | 14 | tp=1 steps=99 |
| C17 | contract | 100 inspections without submit -> truncated=True and empty findings | ✓ | 10 | truncated=True tp=0 fp=0 |
| C18 | contract | time limit: a policy that sleeps past the limit is truncated (61 s; --fast uses 2 s) | ✓ | 3022 | limit=2s slept=3s |
| C19 | contract | closed mode: every reward is 0 and info == {steps_left} | ✓ | 238 | oracle answer scored by the evaluator but invisible to the policy |
| C20 | contract | no leaks in observations, infos, errors, trajectories, paths; traversal attempt fails | ✓ | 236 | 33 blobs scanned, leaks=[] |
| D01 | data | clean book + subscription look-alike | ✓ | 78 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; truth empty, look-alikes=['TWIN_SUBSCRIPTION', 'TWIN_SUBSCRIPTION', 'TWIN_TRUE_PARTIAL', 'TWIN_REFUND'] |
| D02 | data | clean book + split-payment look-alike | ✓ | 87 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; truth empty, look-alikes=['TWIN_SPLIT_PAYMENT', 'TWIN_SPLIT_PAYMENT', 'TWIN_WEEKEND_FX', 'TWIN_BOUNDARY_TZ'] |
| D03 | data | clean book + refund look-alike | ✓ | 86 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; truth empty, look-alikes=['TWIN_SUBSCRIPTION', 'TWIN_TRUE_PARTIAL', 'TWIN_REFUND', 'TWIN_REFUND'] |
| D04 | data | clean book + weekend-FX look-alike | ✓ | 71 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; truth empty, look-alikes=['TWIN_SUBSCRIPTION', 'TWIN_WEEKEND_FX', 'TWIN_WEEKEND_FX', 'TWIN_BOUNDARY_TZ'] |
| D05 | data | clean book + timezone-boundary look-alike | ✓ | 89 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; truth empty, look-alikes=['TWIN_SPLIT_PAYMENT', 'TWIN_REFUND', 'TWIN_BOUNDARY_TZ', 'TWIN_BOUNDARY_TZ'] |
| D06 | data | 1 duplicate invoice + subscription look-alike | ✓ | 66 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 1 duplicates in truth, subscription look-alike present and absent from truth |
| D07 | data | 2 duplicate invoices + look-alike | ✓ | 61 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 2 duplicates in truth, subscription look-alike present and absent from truth |
| D08 | data | 3 duplicate invoices, other base currency | ✓ | 59 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 3 duplicates in truth, subscription look-alike present and absent from truth |
| D09 | data | missing allocation | ✓ | 87 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; kinds=['MISSING_ALLOCATION', 'TWIN_OVERPAYMENT', 'TWIN_TRUE_PARTIAL'] |
| D10 | data | partial allocation | ✓ | 65 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; kinds=['PARTIAL_ALLOCATION', 'TWIN_OVERPAYMENT', 'TWIN_TRUE_PARTIAL'] |
| D11 | data | missing + partial + split-payment look-alike | ✓ | 66 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; kinds=['MISSING_ALLOCATION', 'PARTIAL_ALLOCATION', 'TWIN_SPLIT_PAYMENT'] |
| D12 | data | wrong FX date | ✓ | 36 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 2 fx issues recomputed from raw rows by policy |
| D13 | data | wrong FX rate + weekend look-alike | ✓ | 43 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 1 fx issues recomputed from raw rows by policy |
| D14 | data | period cutoff, tz +05:00 | ✓ | 69 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; tz=+05:00: look-alike looks like next month by eye, is in-period by manifest tz |
| D15 | data | period cutoff, tz -04:00 | ✓ | 67 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; tz=-04:00: look-alike looks like next month by eye, is in-period by manifest tz |
| D16 | data | INT1 (partial payment in foreign currency at the boundary) | ✓ | 58 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 1 interacting groups, both issues of each in truth with their own sums |
| D17 | data | INT1, other base currency | ✓ | 56 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 1 interacting groups, both issues of each in truth with their own sums |
| D18 | data | 2 x INT1 | ✓ | 50 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 2 interacting groups, both issues of each in truth with their own sums |
| D19 | data | INT1 + 2 x INT2 + background errors up to 12 | ✓ | 52 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 3 interacting groups, both issues of each in truth with their own sums |
| D20 | data | INT1 x2 + INT2 + background errors | ✓ | 52 | selfcheck=17/17 scan==truth:True oracle F1=1 reward=0.98; 3 interacting groups, both issues of each in truth with their own sums |
| M01 | reward | full correct answer with evidence, 10 steps -> 0.98 | ✓ | 10 | reward=0.980000000000 tp=1 |
| M02 | reward | silence on an erroneous book is strictly worse than M01 (about -1) | ✓ | 10 | reward=-1.000000000000 |
| M03 | reward | silence on a clean book -> 0.98 | ✓ | 9 | reward=0.980000000000 |
| M04 | reward | false accusation on a clean book is worse than silence, F1 = 0 | ✓ | 14 | reward=-1.000000000000 f1=0 |
| M05 | reward | correct answer plus its duplicate: FP +1 and lower reward | ✓ | 20 | 0.313333333333 < 0.980000000000 |
| M06 | reward | 'flag everything' (30 findings) gives a negative reward | ✓ | 20 | reward=-0.874967741935 fp=29 |
| M07 | reward | wrong type -> FP + FN | ✓ | 10 | tp=0 fp=1 fn=1 |
| M08 | reward | amount off by one minor unit -> FP + FN (tolerance 0) | ✓ | 21 | +1: 0/1/1  -1: 0/1/1 |
| M09 | reward | foreign currency or lower-case code -> FP + FN | ✓ | 21 | other=USD lower=kzt |
| M10 | reward | affected_ids subset or superset -> FP + FN | ✓ | 23 | subset and superset rejected |
| M11 | reward | no evidence or an incomplete evidence set -> FP + FN | ✓ | 18 | empty and incomplete evidence rejected |
| M12 | reward | evidence superset: accepted when every id exists, FP if one does not | ✓ | 24 | existing: tp=1  unknown id: tp=0 |
| M13 | reward | ID with a space or different case -> FP + FN | ✓ | 18 | exact string comparison |
| M14 | reward | 31 findings -> reward -1 | ✓ | 9 | reward=-1.000000000000 |
| M15 | reward | 11 evidence ids -> reward -1 | ✓ | 8 | reward=-1.000000000000 |
| M16 | reward | explanation of 1001 code points -> -1 (1000 is accepted) | ✓ | 17 | 1001 -> -1.000000000000, 1000 -> tp=1 |
| M17 | reward | amount as '100', true or 100.0 -> -1 | ✓ | 30 | string, bool and float rejected |
| M18 | reward | second submit is an error and does not change the first reward | ✓ | 9 | EPISODE_DONE, reward unchanged |
| M19 | reward | the same answer at 10 and at 50 steps differs by exactly 0.08 | ✓ | 20 | 0.980000000000 - 0.900000000000 |
| M20 | reward | ambiguous matching (2 findings <-> 2 issues, cross candidates): maximum matching, order independent | ✓ | 0 | outcomes=1 tp={2} |
| P01 | paired | D01: reorder | ✓ | 406 | reorder: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P02 | paired | D02: reorder | ✓ | 364 | reorder: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P03 | paired | D03: reorder | ✓ | 351 | reorder: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P04 | paired | D04: reorder | ✓ | 354 | reorder: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P05 | paired | D05: reorder | ✓ | 358 | reorder: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P06 | paired | D06: rename_ids | ✓ | 430 | rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P07 | paired | D07: rename_ids | ✓ | 419 | rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P08 | paired | D08: rename_ids | ✓ | 406 | rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P09 | paired | D09: rename_ids | ✓ | 446 | rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P10 | paired | D10: rename_ids | ✓ | 446 | rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P11 | paired | D11: reorder + rename_ids | ✓ | 464 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P12 | paired | D12: reorder + rename_ids | ✓ | 419 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P13 | paired | D13: reorder + rename_ids | ✓ | 450 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P14 | paired | D14: reorder + rename_ids | ✓ | 471 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P15 | paired | D15: reorder + rename_ids | ✓ | 435 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P16 | paired | D16: reorder + rename_ids | ✓ | 431 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P17 | paired | D17: reorder + rename_ids | ✓ | 422 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P18 | paired | D18: reorder + rename_ids | ✓ | 406 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P19 | paired | D19: reorder + rename_ids | ✓ | 528 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |
| P20 | paired | D20: reorder + rename_ids | ✓ | 510 | reorder+rename: reward 0.980000000000 == 0.980000000000; all four conditions hold |

## Допущения и трактовка (читать вместе с отчётом)

- Все 80 проверок — наша трактовка опубликованных блоков жюри; «20/20 у нас» не означает 20/20 у жюри.
- Формат действия: `{"action": name, ...params}` (также принимаются `args` и `name/arguments`).
- `list_records(limit>50)` и `limit<1` → `BAD_ARGS` и шаг списан (без тихой обрезки).
- `submit.episode_id` необязателен; при несовпадении с manifest ответ структурно неверен (−1). Лишние ключи в выводе игнорируются.
- Усечение (100 шагов без submit или 60 с) оценивается как submit пустого ответа; награда по формуле (на чистой книге = 0.8).
- Шаг с ошибкой считается инспекцией; `submit` не входит в `inspection_steps`, но входит в лимит 100.
- Сумма `payment_allocation` — в валюте платежа и считается точно из публичных записей (см. DESIGN.md); τ = 0.
- Лишние `evidence_ids` допустимы, только если все существуют и набор ⊇ одного допустимого; иначе вывод — FP.
- C-проверки изолированы try/except, а не процессами; C18 идёт параллельно с остальными (флаг `--fast`: лимит 2 с).
- M20 проверяет matcher на синтетическом наборе, потому что в сгенерированном эталоне два issue не бывают неразличимыми (I10).
- P-проверки сравнивают oracle до/после преобразования с обратным маппингом ID; новые ID намеренно сортируются иначе.

## Примечания прогона

- --fast: лимит времени в C18 заменён на 2 с
