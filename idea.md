# Supplement Slot Planner MVP

## TL;DR

Минимальная система: агент или человек заполняет простые YAML-карточки subject (substance) через `traits`, а `planner.py` на основе декларативных `traits.yaml` и `slots.yaml` раскладывает активный inventory по 4 слотам с учётом еды, времени, конфликтов и балансировки. Operator управляет полкой substances + dose + brand через единый файл `inventory.yaml`.

---

## 1. Проблема

Есть набор supplements / БАДов, которые нужно принимать в течение дня.

У каждого продукта могут быть простые признаки:

- лучше с едой;
- лучше натощак;
- жирорастворимый;
- энергетизирующий;
- поддерживает сон;
- похож на железо / магний / кальций;
- требует ручного внимания;
- является комплексом.

Нужно автоматически разложить активный недельный стек по 4 слотам, не заставляя человека или агента вручную думать о слотах.

---

## 2. Цель MVP

Сделать минимальную систему без БД и UI:

```text
YAML-файлы → planner.py refresh → planner.py check → planner.py plan → schedule.yaml
```

Система должна:

1. хранить карточки substances в простом YAML;
2. позволять агенту легко создавать карточки;
3. не требовать от карточки знания о слотах;
4. хранить смысл traits в одном месте;
5. хранить слоты декларативно;
6. раскладывать active inventory по 4 слотам;
7. учитывать hard-blocks, soft-levels, conflicts и балансировку;
8. оставлять путь к расширению: Substance↔Product split, evidence, dose, solver.

---

## 3. Не-цели MVP

В MVP не делаем:

- UI;
- БД;
- графовую БД;
- векторную БД;
- медицинскую онтологию;
- ручные веса в карточках;
- слот-правила внутри карточек;
- evidence/confidence grading;
- product-level карточки (см. §24 — следующая фаза);
- модель доз (только свободная строка в inventory);
- drug interactions taxonomy;
- оптимизацию через OR-Tools;
- историю самочувствия / метрик.

---

## 4. Основной принцип

Карточка substance описывает только substance:

```text
"что это за вещество?"
```

Скрипт решает:

```text
"когда (в какой слот) это положить?"
```

Operator решает:

```text
"что у меня есть, что я принимаю, в какой дозе, от кого?"
```

То есть substance card НЕ содержит:

```yaml
slots:
  morning_food: prefer
dose: "400 mg"           # это в inventory
brand: "NOW Foods"       # это в inventory
```

А содержит:

```yaml
traits:
  - "intake:requires_food"
  - "class:fat_soluble"
```

---

## 5. Архитектура файлов

```text
data/
  slots.yaml
  traits.yaml
  inventory.yaml          # operator-facing полка (см. §15)
  products/               # карточки substances; будут переименованы в data/substances/ — см. §24
    vitamin_d3_k2.yaml
    magnesium_glycinate.yaml
    ...

schema/
  slots.schema.json
  traits.schema.json
  product.schema.json
  inventory.schema.json

planner.py        # CLI: check + refresh + plan (PEP 723 inline metadata for uv)
brief.md          # инструкция для агента-заполнителя substance карточек
```

---

## 6. Кто за что отвечает

| Файл | Что это | Кто редактирует | Меняется |
|---|---|---|---|
| `data/slots.yaml` | 4 слота (время + еда) | Ты | Очень редко |
| `data/traits.yaml` | Закрытая таксономия traits + описания + applies_when | Ты (или агент по запросу) | При расширении категорий |
| `data/products/<id>.yaml` | Карточка одной substance — traits, notes. См. §13. Сегодня лежит под `products/`, но описывает substance. См. §24 о planned rename. | Агент по твоему запросу | При добавлении нового supplement |
| **`data/inventory.yaml`** | **Полка: ВСЕ известные substances + active + dose + brand. Главный operator-facing файл.** | **Только ты** (planner.py refresh добавляет новые) | Каждую неделю |
| `schedule.yaml` (генерится) | Раскладка по слотам — выход planner.py plan | Никто | По запросу |

---

## 7. CLI

```text
uv run planner.py check                          # validate всё (schemas + cross-refs + inventory alignment)
uv run planner.py check data/products/foo.yaml   # одну карточку (без inventory cross-check)
uv run planner.py refresh                        # добавить недостающие cards в inventory.yaml как {active: false}
uv run planner.py plan                           # построить schedule.yaml (запускает check неявно) — пока заглушка
```

Exit codes: `0` = успех, не-0 = ошибки. Подходит для CI и для self-check агентами.

---

## 8. Runtime flow

```text
planner.py check:
1. Загрузить slots.yaml → JSON Schema validation.
2. Загрузить traits.yaml → JSON Schema validation.
3. Проверить namespace каждого trait — префикс из закрытого списка (см. §11).
4. Проверить trait.separate_from[] — все ссылки существуют.
5. Проверить trait.effects[].match keys — все имена существуют как поля слотов.
6. Schema гарантирует: в каждом effect либо level (из enum), либо block: true (oneOf).
7. Загрузить substance cards → JSON Schema validation.
8. Проверить, что product.id == filename stem.
9. Проверить уникальность product.id среди всех карточек.
10. Проверить product.traits[] — все ссылки существуют в traits.yaml.
11. Если есть unmatched_concerns — печатать как INFO (не ошибка).
12. Загрузить inventory.yaml → JSON Schema validation.
13. Cross-check: каждая card имеет запись в inventory (иначе ERROR с подсказкой "run refresh").
14. Cross-check: каждая запись inventory имеет card (иначе ERROR с путём ожидаемого файла).

planner.py refresh:
1. Загрузить inventory.yaml.
2. Сканировать data/products/*.yaml.
3. Добавить недостающие записи как {active: false} (existing trogать не trogает).
4. Записать обратно. PyYAML normalizes formatting — кавычки и пустые строки могут пропасть.

planner.py plan (пока заглушка):
1. Запустить check (если ошибки — стоп).
2. Раскладывать только substances с inventory.supplements[id].active == true.
3. Сохранить schedule.yaml.
```

---

## 9. Слоты

`data/slots.yaml`:

```yaml
version: 1

slots:
  morning_empty:
    label: "Morning / empty stomach"
    order: 1
    time: morning
    food: false

  morning_food:
    label: "Morning / with food"
    order: 2
    time: morning
    food: true

  day_food:
    label: "Day / with food"
    order: 3
    time: day
    food: true

  evening_empty:
    label: "Evening / empty stomach"
    order: 4
    time: evening
    food: false
```

Скрипт не имеет отдельных списков `FOOD_SLOTS` / `NO_FOOD_SLOTS`. Свойства слотов — единственный источник.

---

## 10. Score scale

Effect внутри trait использует **именованный enum уровней** + отдельный `block` для hard constraint:

| Level / flag      | Семантика                                            |
|-------------------|------------------------------------------------------|
| `prefer_strong`   | Сильное предпочтение слота (eg. D3 + еда)            |
| `prefer`          | Мягкое предпочтение                                  |
| `avoid`           | Лучше не класть, но допустимо                        |
| `avoid_strong`    | Очень нежелательно                                   |
| `block: true`     | Hard constraint — этот слот никогда                  |

`block` **не уровень шкалы** — это другой механизм. Schema требует **либо** `level`, **либо** `block: true` в каждом effect (oneOf).

Числовые веса для balance/scoring живут только в `planner.py` и не светятся в YAML. Маппинг в коде — простая монотонная функция (e.g., `prefer_strong=4, prefer=2, avoid=-2, avoid_strong=-4`). Менять при необходимости в одном месте.

---

## 11. Trait namespaces

Каждый trait имеет префикс `<namespace>:<identifier>`. **Закрытый список зарегистрированных namespaces:**

| Namespace   | Назначение                                   | Примеры                                           |
|-------------|----------------------------------------------|---------------------------------------------------|
| `intake:`   | Взаимодействие с едой                        | `intake:requires_food`, `intake:prefers_empty_stomach` |
| `effect:`   | Фармакологический эффект (для time-of-day)   | `effect:energy_like`, `effect:sleep_support`, `effect:nootropic` |
| `class:`    | Химический/нутриционный класс                | `class:fat_soluble`, `class:b_vitamin`, `class:electrolyte` |
| `family:`   | Семья для конкуренции абсорбции (separate_from) | `family:iron_like`, `family:magnesium_like`    |
| `risk:`     | Маркеры для warnings                         | `risk:manual_review`                              |

> Раньше существовал `product:` namespace с единственным trait'ом `product:multicomponent`. Trait был удалён (marker без scheduling effects, multicomponent сигнализируется наличием `components:` блока в карточке). Namespace больше не зарегистрирован — `product:*` traits отвергаются валидацией. После Substance↔Product split (§24) namespace может вернуться с другой семантикой.

**Правило:** новый namespace вводится только обновлением этого списка + соответствующих traits в traits.yaml. `planner.py check` падает на нерегистрированный префикс.

В MVP namespaces не имеют формальной семантики (mutually-exclusive и т.п.) — это post-MVP.

---

## 12. Traits

Каждый trait обязан иметь `label`, `description`, `applies_when`. Это критично для агентов, заполняющих карточки.

`data/traits.yaml` (фрагмент):

```yaml
version: 1

traits:
  "intake:requires_food":
    label: "Requires food"
    description: "Активное вещество требует приёма с пищей — без еды плохо усваивается, раздражает желудок, или эффект значительно ослаблен."
    applies_when: "Жирорастворимые витамины (D3, K2, A, E), некоторые минералы с раздражающим действием. НЕ применять к веществам, которые просто 'допустимо с едой' — для этого есть intake:prefers_food."
    effects:
      - match: {food: true}
        level: prefer_strong
      - match: {food: false}
        block: true
```

Полный список traits — в `data/traits.yaml`.

---

## 13. Substance card (сегодня под `data/products/`)

> **Терминологическая заметка.** Сегодня эти карточки лежат в `data/products/` и валидируются schema `product`. Но они описывают **substance** — конкретное вещество с его химией, формой, traits — без указания дозы и бренда. Реальный продукт («банка с наклейкой» — например, "NOW Foods Magnesium Glycinate 400mg") — это будущая сущность, см. §24. То, что сегодня называется "product card", после миграции переедет в `data/substances/` и будет называться substance card. Семантически это уже substance — physical product это другая сущность.

**Substance** — вещество как таковое (cholecalciferol, magnesium glycinate, methylcobalamin). Описывается traits.

**Product (будущее)** — банка в твоём шкафу с наклейкой бренда и дозой. Сегодня роль product выполняет inventory entry.

Поля substance card:
- `id` (req) — машиночитаемый id, snake_case, уникальный, **должен совпадать с filename stem**.
- `name` (req) — человекочитаемое имя.
- `traits` (req) — список trait-id из traits.yaml.
- `components` (opt) — для multicomponent (legacy, см. §14).
- `notes` (opt) — свободные заметки.
- `unmatched_concerns` (opt) — список строк, сигналы для расширения taxonomy.
- `prefer_with` (opt) — список substance ids, с которыми желательна co-location в одном слоте (см. §17.1). Symmetric soft synergy.

**НЕ должно быть в substance card:** `dose:`, `brand:`. Они живут в `inventory.yaml`. После Substance↔Product split (§24) они будут жить в product cards.

Пример (`data/products/vitamin_d3_k2.yaml`):

```yaml
id: vitamin_d3_k2
name: "Vitamin D3 + K2"

traits:
  - "class:fat_soluble"
  - "intake:requires_food"

notes: "Жирорастворимая комбинация. Принимать с приёмом, содержащим жиры."
```

---

## 14. Multicomponent (B-комплекс и т.п.) — legacy workaround

> **Текущее состояние:** карточки multicomponent имеют `components:` как opaque dict (`{vitamin_b1: "50 mg", ...}`) без traits на каждом компоненте. Multicomponent сигнализируется наличием `components:` блока (раньше также trait'ом `product:multicomponent`, удалённым в текущей итерации). Это honest workaround до §24.

После Substance↔Product split: multicomponent станет естественным — product card ссылается на множество substances с их дозами, traits аггрегируются.

Пример сегодня:

```yaml
id: b_complex
name: "B-Complex"

traits:
  - "class:b_vitamin"
  - "intake:prefers_food"

components:
  vitamin_b1: "50 mg"
  vitamin_b6: "25 mg"
  vitamin_b12: "500 mcg"
```

`class:b_vitamin` сейчас — pure marker (без scheduling effects); `effect:energy_like` ранее присутствовал, удалён по folklore-cleanup (B-витамины как «энергизирующие» — не подтверждено фармакологически). Если operator ощущает у себя стимуляцию — добавляет `effect:energy_like` через personal override в inventory (см. §15.1).

После §24 это станет product card ссылающийся на substance cards `vitamin_b1`, `vitamin_b6`, `vitamin_b12` с их дозами; traits аггрегируются автоматически с substance-уровня.

---

## 15. Inventory

`data/inventory.yaml` — операторская полка. Все известные substances + state.

```yaml
version: 1

supplements:

  vitamin_d3_k2:
    active: true
    dose: "5000 IU + 100 mcg"
    brand: "NOW Foods"

  magnesium_glycinate:
    active: true
    dose: "400 mg"
    brand: "Doctor's Best"

  lions_mane_sonnet:
    active: false

  nattokinase:
    active: false
```

Поля per-entry:
- `active` (req bool) — принимаешь ли сейчас.
- `dose` (opt str) — свободная форма ("400 mg", "5000 IU + 100 mcg").
- `brand` (opt str) — производитель.
- `notes` (opt str) — заметки оператора (пауза, эксперимент, etc).

**Жизненный цикл:**

1. Агент создаёт substance card (`data/products/<id>.yaml`).
2. Operator запускает `planner.py refresh` → запись `{active: false}` появляется в inventory.
3. Operator вручную ставит `active: true` + заполняет dose/brand при начале приёма.
4. Removed substances остаются с `active: false` (не теряются, можно вернуть).
5. Schedule (§20) раскладывает только active.

### 15.1. Personal trait overrides

Inventory entry может включать `traits_override` — declarative механизм для personal sensitivity, не покрытой universal traits в `traits.yaml`.

```yaml
supplements:
  b_complex:
    active: true
    dose: "B-complex 50"
    brand: "NOW Foods"
    traits_override:
      add:
        - "effect:energy_like"     # лично у меня действует стимулирующе
      remove:
        - "intake:prefers_food"    # лично переношу натощак
```

Поля `traits_override`:
- `add: [trait_id, ...]` — traits, которые применяются к этому substance в дополнение к карточным.
- `remove: [trait_id, ...]` — traits, объявленные в карточке, но игнорируемые при scoring у этого operator-а.

Хотя бы одно из `add` / `remove` должно присутствовать (schema требует `minProperties: 1` на `traits_override`).

**Зачем это:** universal taxonomy в `traits.yaml` — это «что подтверждено фармакологически или хорошо известно для всех». Personal sensitivity (например «у меня B-комплекс энергизирует, хотя evidence слабая») живёт в operator's inventory, не в universal substance card. Это разделяет «доменное знание» (traits.yaml + cards) от «личной чувствительности» (inventory).

**Применение во время scoring** (planner.py plan, когда будет реализовано):

```text
effective_traits(substance) = (card.traits ∪ inventory[id].traits_override.add)
                             − inventory[id].traits_override.remove
```

Hard constraints (block, separate_from) подчиняются этой формуле — добавленные через `add` traits начинают блокировать слоты; убранные через `remove` traits перестают.

**Что НЕ делает override:**
- Не назначает substance в конкретный slot (это нарушило бы декларативную модель).
- Не задаёт numeric weight overrides (declarative trait-level only).
- Не переопределяет other operator's behavior — это однопользовательская система.

**Где это упомянуто в brief.md:** агенты знают про существование механизма, но не используют — overrides operator-only. Агент пишет универсальную substance card.

---

## 16. Match semantics

Effect:

```yaml
- match:
    food: true
    time: morning
  level: prefer
```

Матчится со слотом, если **все** указанные поля совпадают (AND-only в MVP).

Пример: слот с `time: morning`, `food: true` подходит и под `match: {food: true}`, и под `match: {food: true, time: morning}`.

---

## 17. Conflict semantics

Если trait A содержит:

```yaml
separate_from:
  - "family:magnesium_like"
```

то substances с trait A и substances с `family:magnesium_like` **нельзя** класть в один слот.

`separate_from` **симметричен**. Декларируется один раз, planner трактует двусторонне. Не нужно дублировать в обратную сторону.

В MVP `separate_from` — hard constraint.

### 17.1. Prefer-with semantics (synergy)

Substance card может объявить `prefer_with: [other_substance_id, ...]` — мягкое предпочтение co-location с указанными substances в одном слоте.

```yaml
# data/products/creatine.yaml
id: creatine
name: "Creatine monohydrate"
traits:
  - "intake:prefers_empty_stomach"
prefer_with:
  - "l_citrulline_malate"
```

**Поведение:**
- **Symmetric.** Декларируется в одну сторону, planner трактует двусторонне (declaration в `creatine` действует и для `l_citrulline_malate`).
- **Soft, не hard.** Не блокирует и не форсирует ничего — просто +`PREFER_WITH_BONUS` (=3) к total_score, если оба substance находятся в одном слоте.
- **Действует только между active substances.** Inactive substance в inventory игнорируется (бонус не считается даже если карточка содержит prefer_with на него).
- **Self-reference запрещён** schema-валидатором.
- **Cross-ref валидируется** `planner.py check` — target substance card должен существовать в `data/products/`.

**Зачем:** ситуация когда substance physically принимаются вместе (один стакан воды, единая порция), но это не intake constraint и не trait сам по себе. Например, pre-workout стек «creatine + L-citrulline + (опционально) tadalafil» — все эти вещества independently работают, но удобнее принимать одной порцией.

**Что не делает:**
- Не двигает substance в конкретный слот (декларативность сохраняется — solver сам найдёт лучшее размещение с учётом бонуса).
- Не учитывает «частично co-located» — бонус either applies (in same slot) or doesn't (different slots).
- Не транзитивен. Если `A prefer_with B` и `B prefer_with C`, бонус для `A↔C` не подразумевается — нужна явная декларация.

---

## 18. Balance

Planner старается распределять substances равномернее.

Финальный score:

```text
total_score = sum(slot_level_scores) - balance_penalty
balance_penalty = BALANCE_WEIGHT * sum(slot_load^2)
```

Default `BALANCE_WEIGHT = 0.5`. Тюнится константой в planner.py.

В output `schedule.yaml.explanations` для каждой substance показываются `slot_score` и итоговый `balance_penalty` раздельно — для отладки калибровки.

Hard constraints (`block`, `separate_from`) важнее balance.

---

## 19. Search strategy

MVP — backtracking с упорядочиванием по размеру domain:

```text
1. Для каждой active substance посчитать допустимые слоты (после фильтрации block + separate_from).
2. Сначала раскладывать substances с меньшим числом допустимых слотов.
3. Рекурсивно назначать substance в слот.
4. Считать score, отбрасывать варианты-нарушения separate_from.
5. Вернуть лучший вариант.
```

Для 10–20 substances и 4 слотов достаточно.

---

## 20. Output

`schedule.yaml`:

```yaml
version: 1

total_score: 42

slots:
  morning_empty: []

  morning_food:
    - vitamin_d3_k2

  day_food: []

  evening_empty:
    - magnesium_glycinate

warnings:
  - substance: iron_bisglycinate
    trait: "risk:manual_review"
    message: "Requires manual review."

explanations:
  vitamin_d3_k2:
    slot: morning_food
    slot_score: 6
    balance_penalty: -2.0
    reasons:
      - "intake:requires_food matched food=true → prefer_strong"
      - "class:fat_soluble matched food=true → prefer"
```

Schedule показывает substance ids. Дозы здесь не показываются (печатать на холодильник не планируется; dose живёт в inventory).

---

## 21. JSON Schemas

Все YAML kinds покрыты JSON Schema (`schema/*.schema.json`):

- `slots.schema.json` — slots.yaml.
- `traits.schema.json` — traits.yaml (включает enum levels и oneOf [level, block] на каждый effect).
- `product.schema.json` — единичная substance card (имя schema legacy, см. §13).
- `inventory.schema.json` — inventory.yaml (dict с обязательным `active` per entry).

Schema проверяет shape. Доменные ссылки (trait existence, namespace registration, id-filename match, id uniqueness, inventory↔card alignment) проверяются дополнительно в `planner.py check`.

---

## 22. Агентское заполнение карточек

Полная инструкция — `brief.md`. Кратко:

```text
Создай YAML SUBSTANCE card (сегодня лежит в data/products/).

Описывает substance — вещество, не реальный продукт.
НЕ указывай dose, brand, slots, weights, levels.
Используй только traits из traits.yaml. Не придумывай новые.
Не придумывай новые namespaces (см. §11).
Если не уверен — НЕ добавляй trait. Лучше пустой traits, чем неточный.
unmatched_concerns для taxonomy gaps.
Cite sources (NIH, examine.com, label).

Self-check:
  uv run planner.py check data/products/<id>.yaml
```

Operator потом запускает `planner.py refresh` и заполняет dose/brand в inventory.

---

## 23. Зарезервировано для post-MVP

Имена полей не использовать в MVP под другую семантику:

- `confidence:` (effect/trait) — evidence grading.
- `dose:` (substance card) — НЕ использовать на substance, только в inventory entries и (в будущем) в product cards.
- `brand:` (substance card) — same.
- ~~`prefer_with:`~~ — **реализовано** на substance-level (см. §17.1). Может в будущем расшириться на trait-level.
- `min_distance:` — временной зазор между приёмами.
- `substances:` (product card) — для будущей product сущности (см. §24): `substances: {magnesium_glycinate: {dose: "400 mg"}}`.
- `started:`, `paused_until:`, `lot:` — для будущих inventory entries.

---

## 24. Substance ↔ Product split (planned next phase)

**Терминология:**

- **Substance** — вещество как таковое: химия, форма, traits. Не привязано к бренду или дозе. Например: `magnesium_glycinate`, `cholecalciferol`, `methylcobalamin`. **Сегодня** substance карточки лежат под `data/products/` и валидируются schema `product` — это терминологический legacy, который мы исправим при миграции.
- **Product** — «банка с наклейкой»: реальный продукт в твоём шкафу. Содержит одну или больше substances с их дозами, имеет brand и (опционально) дополнительные ингредиенты. Например: `now_mg_glycinate_400`, `solgar_vit_d3_5000_k2_100`, `now_b_complex` (мультивитамин).

**Будущая структура:**

```text
data/
  substances/<id>.yaml    # бывшие data/products/, переименование
    id, name, traits, notes        # без dose, без brand
  products/<id>.yaml      # новая сущность
    id, name, brand
    substances:
      <substance_id>:
        dose: "400 mg"
  inventory.yaml          # ссылается на product ids (не substance)
```

Пример будущего product card:

```yaml
id: now_mg_glycinate_400
name: "NOW Foods Magnesium Glycinate"
brand: "NOW Foods"
substances:
  magnesium_glycinate:
    dose: "400 mg"
```

Пример будущего multivitamin:

```yaml
id: now_b_complex
name: "NOW Foods B-Complex"
brand: "NOW Foods"
substances:
  vitamin_b1: {dose: "50 mg"}
  vitamin_b2: {dose: "25 mg"}
  vitamin_b6: {dose: "25 mg"}
  vitamin_b12: {dose: "500 mcg"}
  ...
```

**Что элегантно:**

- Multivitamin: один product ссылается на много substances. Traits аггрегируются автоматически из всех substances.
- Один substance — много products (NOW vs Doctor's Best — разные дозы, разные бренды, разные products).
- Dose tracking естественен: на связи product↔substance.
- History/analytics: можно агрегировать intake до substance level (для корреляций с самочувствием).
- Это позволяет различать варианты одного substance с разной дозой и формой.

**Migration cost (когда руки дойдут):**

| Шаг | Цена |
|---|---|
| `git mv data/products data/substances` | секунды |
| Update `PRODUCTS_DIR` const + paths in planner.py | минуты |
| Update brief.md, idea.md (terminology) | минуты |
| Создать `data/products/` + `schema/product.schema.json` (новый, для product сущности) | ~30 минут |
| Расширить planner: trait-aggregation от substances к product | ~1 час |
| Inventory: переписать ids (substance → product) | one-time, ручная миграция данных |

Итого: **layered addition + one-time data migration**, не переписывание. Низкорисково.

---

## 25. Расширение после MVP

1. Substance↔Product split (см. §24 — приоритет).
2. Daily log (`data/log/YYYY-MM-DD.yaml`) — append-only, для аналитики самочувствия.
3. Per-week snapshots inventory (для history).
4. ~~Soft `prefer_with` synergies~~ — **реализовано** на substance-level в текущей версии. Trait-level расширение возможно в будущем.
5. `min_distance` между приёмами одних substances.
6. Evidence/confidence grading (`confidence:` на effect).
7. Drug interaction risks (`risk:blood_thinner_interaction` etc).
8. Constraint solver вместо brute force.
9. Импорт в SQLite/PostgreSQL.
10. UI или agent workflow.
11. Namespace semantics (mutually-exclusive, applies-to-field).
12. `match.any:` для OR-логики в effects.
13. Slot dimension `fat_meal` — тогда вернуть `intake:prefers_fat_meal`.
14. **Vector trait model exploration (deferred).** Панель по trait taxonomy redesign была проведена; решено остаться на discrete trait model + добавить personal overrides (см. §15.1) + folklore-cleanup в `traits.yaml` (drop `class:b_vitamin.effects`, drop `product:multicomponent`, tighten `effect:energy_like.applies_when`). Vector модель (substance как точка в N-мерном пространстве осей food/time/sleep/..., scoring = scalar product / distance) отложена до конкретного будущего use case (cross-substance similarity, continuous gradations, или per-user vector arithmetic) — нет current оправдания для миграции, agent UX regression risk высок. Если соблазн вернётся — сначала найти реальный use case.

---

## 26. Ключевое решение

Единственные источники истины:

```text
slots.yaml      — свойства слотов
traits.yaml     — смысл traits
products/*.yaml — какие traits есть у substance (today; будет substances/ — см. §24)
inventory.yaml  — что у тебя есть, что принимаешь, в какой дозе и от кого
```

Скрипт не содержит доменной логики. Только интерпретирует декларативные данные.
