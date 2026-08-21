# Catalog Migration Inventory — 2026-08-21

## Scope and method

This is a read-only catalog reconciliation for the exact decision refs:

| Side | Commit | Tree |
|---|---|---|
| `origin/main` | `4abac57e8d495e0ad1268af4a7685009e6212975` | `0b1cc807bd7e4fe0c4567df8fd8f2fc9230f90a7` |
| `origin/feature/executable-ontology-contract` | `70940b359d81f6ba7fa102d7d310f08ae43df56b` | `a3caaed869867d1453089f76e90f0b7b33fa148f` |

The inventory compares tracked YAML card IDs, names, brands, forms, component
references, and `data/stacks.yaml`. It does not assess medical evidence. A
stable ID is treated as the identity key; a filename or display-label change is
not by itself a new entity. Classifications mean:

* **real shelf update** — a product/card is newly scheduled or deliberately
  removed from the active shelf;
* **canonical identity replacement** — an existing stable entity is remapped
  to a more specific or consolidated canonical card;
* **deliberate catalog addition/removal** — a new or retired catalog entity,
  not an accidental rename;
* **possible migration artifact** — the repository does not establish intent,
  or a broad family card may have hidden form-level distinctions.

## Cardinality and stable identity

| Entity | `main` | `feature` | Shared IDs | Main-only IDs | Feature-only IDs |
|---|---:|---:|---:|---:|---:|
| Product cards | 59 | 63 | 59 | 0 | 4 |
| Substance cards | 253 | 255 | 252 | 1 | 3 |

All 59 main product IDs remain present on feature, although three formerly
active cards become unassigned and one inactive card becomes active. Product
filenames and labels are therefore not reliable identity keys. The only
main-only substance ID is `sub_yd7dqo36dn`; the three feature-only IDs are
new forms/components used by feature-only products below.

## Product identity and shelf inventory

### Feature-only product IDs

These are four genuine feature catalog additions: each has a new stable
`prd_*` ID, a product card, component links, and membership in the feature
`daily` stack. They are not generated artifacts.

| Product ID | Feature card / components | Classification | Uncertainty |
|---|---|---|---|
| `prd_d0u8k66ypy` | GLS `Ежовик гребенчатый с холином`; Lion’s Mane `sub_e3af6f78d9` + Choline bitartrate `sub_kwudyhex2o` | deliberate catalog addition; real shelf update | Product is Russian-labelled and its source/brand naming is sparse (`gls__product`); exact package provenance remains a data-quality question. |
| `prd_w2s970gps4` | Psalae Antarctiv Krill oil; krill oil, EPA, DHA, phospholipids `sub_t8sx7e49j7`, astaxanthin | deliberate catalog addition; real shelf update | New product is distinct from the retained Nature’s Truth krill card; no evidence here that it replaces that card. |
| `prd_8mvv1w128a` | Psalae Astaxanthin; astaxanthin `sub_249199f726` | deliberate catalog addition; real shelf update | No main counterpart. |
| `prd_htuhz2s2gt` | Solgar Omega-3; fish-oil concentrate `sub_sunkcr05vl`, EPA, DHA | deliberate catalog addition; real shelf update | Ethyl-ester form is explicit in the product label; no main counterpart. |

### Shared product IDs with identity presentation changes

Stable IDs are preserved. The changes are label/file simplifications except
for Picamilon’s source/brand remodeling. They are not separate products.

| Product ID | Main → feature presentation | Components / classification |
|---|---|---|
| `prd_175251bd63` | Airboy: `Nattokinase 6000 FU, 120 caps` → `Nattokinase`; filename simplified | Same component ID; display normalization. |
| `prd_20bf2df267` | TiM: `Electrolyte Caps (multi-electrolyte)` → `Electrolyte Caps` | Same component IDs; display normalization. Training membership unchanged. |
| `prd_8eff2491b7` | BioGrace: `Vitamin B5 (pantothenic acid)` → `Vitamin B5` | Same `sub_7628e4f478`; feature adds label `кальция пантотенат 15 мг` and preserves chemistry at Product level. Canonical presentation simplification, not a new product. |
| `prd_bb212cffc2` | Country Life: long active/coenzymated name → `Coenzyme B-Complex` | One B3 component is corrected from `sub_e9e80d003a` to exact-form `sub_6yp50f6ach`; see component inventory. |
| `prd_eb6337a6dc` | Futurebiotics: `Vitamin D3 (cholecalciferol)` → `Vitamin D3` | Same component; display normalization. `use_pattern` becomes `not_every_day`. |
| `prd_932319251f` | Life Extension: `Only Trace Minerals (multi-trace-mineral complex)` → `Only Trace Minerals` | Same component IDs; display normalization. |
| `prd_9d0fca3201` | Vitamir: `Magnesium glycinate` → `Magnesium` | Same component ID; product label is less form-specific. Possible form-detail loss in presentation; the component card remains the same. |
| `prd_vitamealc8` | VitaMeal: `Vitamin C, 800 mg` → `Vitamin C` | Same component IDs; dose moved out of display name. |
| `prd_7ae9a92d3b` | Farmstandart → Pharmstandard-UfaVITA; same `Picamilon` ID | Same substance ID, but feature adds form `sodium nicotinoyl gamma-aminobutyrate`, label, URLs, and `not_every_day`; inactive → daily. This is a canonical product-source remodeling plus a real shelf update, not a new product ID. |

### Stack membership and expectation changes

Stack counts are: main `daily=12`, `training=4`, `inactive=42`,
unassigned=1; feature `daily=14`, `training=4`, `inactive=41`,
unassigned=4. The complete set of membership changes is:

| Product ID | Main state → feature state | Product | Classification / consequence |
|---|---|---|---|
| `prd_27f7b85aa6` | daily → unassigned | Best Naturals Acetyl L-Carnitine (ALCAR) | Active shelf removal or migration omission; card and components are unchanged. Feature planner reports it unassigned. Intent is not explicit. |
| `prd_c81eb18069` | daily → unassigned | Vitamir Lion’s Mane + B6 Complex | Active shelf removal or migration omission; card and components are unchanged. Feature planner reports it unassigned. Intent is not explicit. |
| `prd_7f04daf970` | daily → unassigned | Nature’s Truth Antarctic Krill Oil | Active shelf removal or migration omission; card and components are unchanged. It is not replaced by the distinct Psalae card at the ID level. |
| `prd_7ae9a92d3b` | inactive → daily | Picamilon | Deliberate shelf reactivation, with `use_pattern: not_every_day`. |
| `prd_d0u8k66ypy` | unassigned → daily | GLS Lion’s Mane + Choline | Real shelf update / new card. |
| `prd_w2s970gps4` | unassigned → daily | Psalae Antarctiv Krill oil | Real shelf update / new card. |
| `prd_8mvv1w128a` | unassigned → daily | Psalae Astaxanthin | Real shelf update / new card. |
| `prd_htuhz2s2gt` | unassigned → daily | Solgar Omega-3 | Real shelf update / new card. |

No product changes to or from `training`; all four training IDs are stable.
The feature branch adds `use_pattern: not_every_day` to exactly three shared
daily products: D3 (`prd_eb6337a6dc`), Country Life B-Complex
(`prd_bb212cffc2`), and Picamilon (`prd_7ae9a92d3b`). Solgar Omega-3 is also
`not_every_day`. This is presentation grouping, not a recurrence, dose, or
calendar model; all remain in the daily scheduling stack.

## Substance identity inventory

### Main-only substance

| ID | Main card | Feature treatment | Classification |
|---|---|---|---|
| `sub_yd7dqo36dn` | Vitamin B5; form `calcium D-pantothenate`; aliases include calcium pantothenate and D-calcium pantothenate | Removed as a standalone card. Feature uses family card `sub_7628e4f478` and records exact product chemistry in Product `label`/`notes`. | Canonical identity consolidation, with a form-specific identity-loss risk. Product-level labels preserve the disclosed form for migrated references, but generic family queries can no longer select this form as its own substance ID. |

### Feature-only substances

| ID | Card identity | Referenced by | Classification |
|---|---|---|---|
| `sub_kwudyhex2o` | Choline; form `bitartrate` | GLS `prd_d0u8k66ypy` | Deliberate catalog addition tied to a new product. |
| `sub_sunkcr05vl` | Fish Oil Concentrate; form `EPA/DHA ethyl esters` | Solgar Omega-3 `prd_htuhz2s2gt` | Deliberate catalog addition tied to a new product; explicit form is retained. |
| `sub_t8sx7e49j7` | Phospholipids; no form | Psalae Antarctiv `prd_w2s970gps4` | Deliberate catalog addition tied to a new product. |

The remaining 252 substance IDs are shared. Comparing identity fields
(`name`, `form`, `aliases`) finds only two shared-ID changes:

* `sub_396c221c31` Picamilon: form absent → `sodium nicotinoyl gamma-
  aminobutyrate`. This is added specificity, not a new identity.
* `sub_7628e4f478` Vitamin B5: form `pantothenic acid` → no top-level form.
  The feature card explicitly says it is a family card and that exact
  chemistry belongs on Products. This is the same B5 consolidation described
  above; it is intentional in the feature model but loses direct
  form-specific substance selection.

Many shared cards gain `scheduling_assessment` and revised notes/knowledge
fields. Those are semantic-enrichment changes, not identity changes, and are
outside this catalog identity inventory.

## Component-reference reconciliation

Only three shared product/component ID sets differ:

| Product | Main component ID(s) → feature component ID(s) | Classification |
|---|---|---|
| `prd_bb212cffc2` Country Life Coenzyme B-Complex | `sub_e9e80d003a` (generic Vitamin B3 / niacin card) → `sub_6yp50f6ach` (Vitamin B3 / inositol hexaniacinate) | Canonical identity correction. Both product labels say inositol hexaniacinate; feature links the exact-form card. This is not a substance loss. |
| `prd_io1peb9syp` Opti-Men (inactive) | `sub_yd7dqo36dn` calcium D-pantothenate → `sub_7628e4f478` B5 family card | Canonical identity consolidation. Product label retains calcium D-pantothenate, but the exact form is no longer a separate substance reference. |
| `prd_qmgu4q8ipo` BioCoenzymated Active B Complex (inactive) | `sub_yd7dqo36dn` calcium D-pantothenate → `sub_7628e4f478` B5 family card | Same B5 consolidation; product label retains calcium D-pantothenate. |

Picamilon keeps `sub_396c221c31`; BioGrace B5 keeps `sub_7628e4f478`.
The four feature-only products add the new component references listed in
their product table; no existing shared component ID is removed from those
products. All other shared product component ID lists are unchanged.

## Verified losses, gains, and unresolved migration questions

### Verified feature gains

* Four explicit product cards and three explicit substance cards are added.
* Picamilon gains source/brand, URLs, explicit chemical form, and episodic-use
  presentation while retaining its stable IDs.
* The B3 inositol-hexaniacinate component is linked to its exact-form card.
* Product labels/notes carry exact B5 chemistry after consolidation to a family
  substance card.

### Verified feature-side losses or behaviorally exposed gaps

* Three main daily cards become unassigned: ALCAR, Vitamir Lion’s Mane+B6, and
  Nature’s Truth Krill Oil. Their cards and component links remain, so this is
  a shelf-membership loss or omission, not entity deletion.
* The standalone `sub_yd7dqo36dn` form identity is absent. Exact B5 chemistry
  survives only as Product-level label/notes on the inspected references.
* The feature daily shelf has 14 products versus main’s 12, but it contains
  four new cards and no longer schedules three previously active cards; this is
  a changed shelf, not a monotonic migration.

### Uncertainty requiring explicit cutover adjudication

* Repository facts do not state whether the three daily→unassigned moves are
  intentional removals, depleted/not-owned status changes, or migration
  omissions. They should not be silently treated as either loss or deliberate
  removal.
* The feature’s B5 family-card model is coherent and documented, but whether
  Product-level labels are sufficient for future form-specific queries is an
  unresolved portability requirement.
* The new GLS/Russian-labelled product has sparse provenance in its filename;
  the card exists and is scheduled, but package/source verification is not
  established by this inventory.

This artifact records catalog facts only. It does not choose a branch, approve
cutover, or authorize deletion of either product line.
