# Executable Ontology Contract Implementation Plan

## 1. Overview

Supp Slotter currently has useful, curated ontology data, but its semantic rules are split between `data/traits/*.yaml`, JSON Schemas, Python constants and validators, and prose in `docs/domain-model.md`.  `planner check` can prove that a slug exists and a reference resolves; it cannot prove that the slug is placed in the semantically valid layer or that the graph satisfies declared ontology constraints.

This feature makes one version-controlled LinkML package the only author-edited ontology source.  It must preserve every useful fact represented by substance and product cards, while allowing cards to change shape when the formal model requires it.  Generated JSON Schema, OWL, SHACL and runtime vocabulary artifacts are derived outputs.  RDFLib and pySHACL provide executable semantic validation; the existing command-scoped SurrealDB `mem://` read model remains the navigation and graph-audit layer.

The branch is an atomic cutover: implementation may use internal migration commits, but the final branch has no legacy ontology registry, handwritten semantic schema, fallback reader, or dual validation path.  There is no requirement for byte-for-byte YAML preservation.  The acceptance bar is preservation and accountable relocation of useful card facts, stable substance/product IDs, and preserved planner behaviour where the ontology does not intentionally correct a semantic placement.

### Approved approach

The approved approach is **LinkML authoring + generated artifacts + RDFLib/pySHACL validation + SurrealDB navigation/audit**.

Alternatives considered and rejected:

| Approach | Why rejected |
|---|---|
| Continue JSON Schema plus new Python `if` checks | Keeps semantic decisions scattered and creates a home-grown ontology framework. |
| OWL-only with Owlready2/OWLAPY | Open-world reasoning is poor at required closed-world card integrity checks; it adds a heavy reasoner without replacing SHACL. |
| Move the source of truth to SurrealDB | Contradicts the Git/YAML-first workflow and turns the existing ephemeral query model into persistent authoring storage. |

### Success criteria

- `ontology/supp_slotter.yaml` and its explicitly imported modules are the sole authoring root for vocabulary, semantic categories, relation semantics, cardinalities, and OntoClean profiles.
- All current substance and product card information is either retained in the migrated card graph or reported as an intentional, reviewed removal.  Stable `sub_*` and `prd_*` IDs remain unchanged.
- Current cards are migrated to the canonical generated card shape; product components continue resolving to substance IDs.
- `planner check` invokes one canonical validation pipeline: generated structural validation plus RDF/SHACL semantic validation and ordinary referential/card checks.  It has no legacy semantic validator fallback.
- Existing planning, review, find and audit commands read generated runtime ontology data rather than legacy traits/constants; SurrealDB remains `mem://` and receives the canonicalized loaded facts.
- The full local and CI gates pass, including new migration-accounting and semantic-negative tests.

## 2. Security Summary

- Attack surface change: slightly increased only for parsing local LinkML/YAML/RDF and running local validation; no network service, listening port, credentials, or persistent database is added.
- New permissions required: none.  LinkML generation and SHACL validation operate on repository files only.
- Sensitive data handling: no new category.  Existing rule remains: personal health history and private operator notes remain outside tracked ontology data.
- Security issues identified: malicious/oversized YAML/RDF causing resource pressure; path traversal through generated-artifact paths; semantic bypass through stale generated artifacts; diagnostic output accidentally echoing private card text.
- Security posture: fail closed.  Missing, stale, malformed, untrusted, or non-deterministically generated ontology artifacts fail `planner check` and CI; no command silently falls back to `data/traits` or old schemas.

## 3. Architecture Impact

### Current state

`data/traits/*.yaml` supplies the trait registry through `planner/cards/traits.py`; `schema/*.schema.json` is loaded by `planner/schema_validation.py`; namespace and display decisions also live in `planner/domain_constants.py`.  `planner/engine/check.py` composes schema, registry, card, relation, product, stack and dashboard validation.  `planner/query_model/surreal.py` creates a fresh SurrealDB `mem://` database per command and `planner/query_model/surreal_records.py` loads cards, traits, relations, dashboards, products and stacks into it.

### Target data flow

```text
author edits
ontology/supp_slotter.yaml + imported ontology modules
                 |
                 | generate (deterministic, repository-local)
                 v
ontology/generated/{schema,shacl,owl,context}.{json,yaml,ttl}
                 |
cards (canonical YAML) -- parse/normalize --> typed card objects
                 |                                  |
                 +---- RDF projection (RDFLib) ------+
                                                    |
                                              pySHACL validate
                                                    |
                                      planner check report (fail closed)
                                                    |
                    generated runtime vocabulary ----+----> planner/review/plan
                                                    |
                  same loaded canonical objects ----> SurrealDB mem:// read model
                                                    |
                                         find/review/audit/navigation
```

The ontology package defines terms and constraints; cards are instances and facts.  SurrealDB does not become an ontology source, validator of record, or persistent store.

## 4. Detailed Design

### 4.1 Canonical ontology package

Create an `ontology/` package with one authoring manifest and explicit imports rather than a monolithic unreviewable file.  "One source of truth" means one reviewed authored package, not a claim that every declarative rule is expressible in LinkML YAML.  The manifest is the only entry point and owns both the LinkML source and the hand-authored SHACL-SPARQL constraints that LinkML cannot generate:

```text
ontology/
  manifest.yaml                     # canonical root: source modules, custom shapes, version
  supp_slotter.yaml                 # LinkML root; imports LinkML YAML modules
  model.yaml                        # Substance, Product, component, relation, dashboard slots
  vocabulary.yaml                   # terms, namespace, semantic category, labels, descriptions
  relations.yaml                    # relation type/domain/range/directionality rules
  ontoclean.yaml                    # rigidity, identity, unity, dependence profiles
  constraints/
    semantic.ttl                    # hand-authored SHACL-SPARQL; listed by manifest only
  generated/                        # deterministic outputs; never hand-edit
    card.schema.json
    ontology.ttl
    shapes.ttl
    runtime-vocabulary.yaml
```

`manifest.yaml` contains the schema version, canonical base IRI, ordered LinkML imports, ordered custom-shape files, generator version and a hash of every authored input.  Generation loads only files named in that manifest, combines LinkML-generated structural shapes with `constraints/semantic.ttl`, and writes a manifest hash/schema version header into every generated artifact.  Thus custom SHACL is an authored ontology rule with a single declared owner, not a shadow Python validator or an undeclared generated-file edit.  Generated files are committed and checked for freshness in CI.  The manifest, its LinkML modules, and its listed authored SHACL-SPARQL files are the complete editable ontology package; no generated file or Python constant is an alternate semantic authority.

Each controlled term has at least: stable slug/URI, human label, description, `semantic_category`, allowed card predicate(s), and optional scheduler/reviewer metadata.  Semantic categories are an explicit closed enum:

| Category | Meaning | Valid card home |
|---|---|---|
| `kind` | rigid classification of a substance | `knowledge.kind` |
| `role` | anti-rigid contextual/functional role | `knowledge.role` |
| `quality` | intrinsic property/value-like characteristic | `knowledge.quality` |
| `effect` | reusable pharmacological/functional assertion | `knowledge.effect` |
| `risk` | safety-review assertion | `knowledge.risk` |
| `pathway` | biochemical participation | `knowledge.pathway` |
| `context` | editorial dashboard membership/projection | dashboard selector or `knowledge.context` only |
| `schedule_rule` | slot-scoring rule | `schedule.intake`, `schedule.timing`, `schedule.activity` |

`Substance` and `Product` are the base entity types.  OntoClean metadata is attached to ontology terms, not inferred from labels.  Profiles are templated by category (rather than manually duplicating five fields across every term): `kind` is rigid and supplies an identity criterion only where the term truly does; `role` and `context` are anti-rigid/dependent; `quality`, `effect`, `risk`, `pathway`, and `schedule_rule` are dependent assertions.  A term records only exceptions and its rationale.  CI requires a complete profile after defaults are expanded.

The migration mapping is an authored, exhaustive `ontology/migrations/v1-term-map.yaml`, generated initially from the old registries and reviewed before any card rewrite.  It maps each old `namespace:slug` to exactly one new predicate/slug, with a rationale and optional `intentional_drop` reason.  It is paired with `ontology/migrations/v1-relation-map.yaml`: one entry for **every** source relation record, keyed by its source file and stable ID (or canonical source-record hash), with the old endpoints, normalized typed selectors, relation type, directionality and any approved relocation.  The relation-map loader must enumerate and reject every legacy endpoint form—`source_name`/`target_name`, `source_substance`/`target_substance`, `source_trait`/`target_trait`, and `source_class`/`target_class`—unless that exact input record has an entry.  No generic fallback or default conversion is allowed.  The first committed data-preservation baseline is generated before any card data edit.  Required initial decisions include:

| Existing term group | Canonical placement |
|---|---|
| `is:mineral`, `amino`, `carotenoid`, `flavonoid`, `fiber`, `protein`, `vitamin`, `enzyme`, `hormone`, `botanical`, `omega3`, `bile_acid`, `nucleotide`, `glycosaminoglycan`, `carbohydrate`, `alkaloid`, `phytosterol`, `fatty_acid_derivative`, `probiotic` | `knowledge.kind` |
| `is:adaptogen`, `antioxidant`, `ergogenic`, `nootropic`, `pharmaceutical` | `knowledge.role` |
| `is:fat_soluble`, `is:electrolyte` | `knowledge.quality` |
| every existing `effect:*` | map explicitly in `v1-term-map.yaml`: default stays `knowledge.effect`; a term moves to `knowledge.context` only when it is purely editorial dashboard membership, never merely because its slug ends `_context` |
| `risk:*`, `pathway:*`, schedule traits | same semantic predicate (`risk`, `pathway`, `schedule.*`) unless the complete mapping explicitly says otherwise |

No automatic classifier may silently decide a term's semantics.  The exhaustive maps are themselves checked: old registry term set equals term-map input set; old relation-record set equals relation-map input set; every mapped target exists in the canonical vocabulary; no card fact or relation is rewritten until its mapping exists.

Before baseline capture, commit `planner/ontology/migration_normalize.py` and `tests/test_ontology_normalize.py` as the single comparison normalizer.  Its semantics are fixed and tested: parse YAML values into typed canonical JSON; normalize Unicode strings to NFC and line endings to `\n`; represent mappings as lexicographically sorted key/value pairs; preserve ordered sequences in source order; represent declared set-like fields as sorted **multisets** (so duplicate facts cannot disappear); preserve numbers as their parsed decimal lexical value and booleans/null as typed values; and emit every fact as `(entity-ID, source-field path, typed normalized value)`.  The baseline, post-cutover cards, term-map, relation-map and accounting report all consume this same versioned normalizer.  Comparisons are exact multiset equality of normalized facts except for an explicit mapping entry marked `relocated`, `consolidated`, or `intentional_drop` with rationale and source/target fact keys; a missing, extra, changed, or ambiguously matched fact fails.  Tests must prove normalization is deterministic and must distinguish absent, null, empty string, empty list, duplicate list item, numeric string and numeric value.

### 4.2 RDF identity and projection contract

`ontology/manifest.yaml` fixes the base IRI to `https://j2h4u.github.io/supp-slotter/ontology/v1/`; the LinkML `id`, generated JSON-LD context, generated SHACL/OWL namespaces, runtime RDFLib prefix `ss`, and every hand-authored SHACL-SPARQL query must use that exact value.  Generation rejects a source or generated artifact with a different `ss` namespace.  The projection is deterministic: repository-relative card paths are never RDF identities.  The following table is normative for `planner/ontology/rdf.py`, generated shapes, and every hand-authored SHACL-SPARQL query.

| Repository fact | RDF subject | Predicate | RDF object | Notes |
|---|---|---|---|---|
| ontology term `category:slug` | `<base>/term/{category}/{slug}` | `rdf:type`, `ss:semanticCategory`, OntoClean predicates | category URI, literals | One stable URI per controlled term. |
| substance `sub_*` | `<base>/substance/{id}` | `rdf:type ss:Substance`; `ss:hasKind/Role/Quality/Effect/Risk/Pathway/Context` | term URI | All knowledge facts use the predicate corresponding to their canonical category. |
| product `prd_*` | `<base>/product/{id}` | `rdf:type ss:Product`; label/provenance predicates | literals | Stable ID, never filename, supplies identity. |
| product component | product URI | `ss:hasComponent` | reified component URI | Component URI is `<base>/component/{prd_id}/{index}` and has `ss:substance` to the `sub_*` URI, amount/unit/form literals. |
| relation record | `<base>/relation/{stable-record-id-or-deterministic-hash}` | `rdf:type ss:{RelationType}`; `ss:sourceSelector`, `ss:targetSelector` | selector URI | Relation identity is stable record ID when present, otherwise a canonical hash of its normalized source file fact. |
| typed selector | `<base>/selector/{relation-id}/{side}` | `ss:selectorCategory`, `ss:selectsTerm` | category URI, term URI | Never overload a class endpoint for a trait/quality. |
| dashboard | `<base>/dashboard/{slug}` | `rdf:type ss:Dashboard`; `ss:hasSelector` | selector URI | Dashboard rules are projections, not copied inferred facts. |
| stack/pillbox fact | `<base>/stack/{id}` or `<base>/pillbox/{id}` | typed schedule/component predicates | canonical entity URI/literal | Only facts needed by declared constraints are projected. |

Projection serializes sorted normalized values and skolemizes no blank nodes, so its triples, SHACL focus nodes and diagnostics are stable across runs.  It projects enough source-path metadata to map a validation result to a card path without placing raw notes or unneeded private prose in the graph.

### 4.3 Canonical card model and migration rules

The generated LinkML model owns the structural form now duplicated in `schema/substance.schema.json`, `schema/product.schema.json`, `schema/relations.schema.json`, `schema/dashboard.schema.json`, `schema/stacks.schema.json`, `schema/pillboxes.schema.json`, and `schema/traits.schema.json`.

Substance cards retain their current identity and narrative data: `id`, `name`, `form`, `aliases`, `notes`, `concerns`, scheduling data and knowledge data.  Their knowledge predicate names become semantic rather than historical:

```yaml
knowledge:
  kind: [mineral]
  role: [nootropic]
  quality: [fat_soluble]
  effect: [pde5_inhibition]
  risk: [bleeding_med_interaction]
  pathway: [nitric_oxide_cgmp]
```

This is illustrative; the actual allowed fields come only from generated schema/runtime vocabulary.  `context` remains only for genuinely extensional curated membership; derived dashboard membership is stored as a dashboard selector, not copied into cards.

The context/dashboard contract is explicit: a `knowledge.context` fact is an authored extensional membership and must resolve to exactly one dashboard whose manifest declares that context; a dashboard `from_traits`/selector is an intensional projection and must reference registered canonical predicates/terms but does not authorize copying a derived context fact onto every matching substance.  `dashboard` is therefore an authored projection class in the model, not a historical trait namespace or a ninth `knowledge.*` classification.

Product cards remain physical-label facts and preserve their stable ID, components, brand, URL, notes, amounts and provenance.  Product components continue to use canonical `sub_*` references.  Blends remain substance cards only where they are reusable scheduler/review entities; otherwise their label information remains product-card notes/components.  The migration inventory records every blend decision.

Relations use one generic typed selector endpoint model rather than separate ambiguous `source_class`, `source_trait`, and name fields.  A selector is `{category, term}` (for ontology-backed matching) or `{entity, id/name}` (for explicit substance/name matching); relation type metadata declares the exact allowed selector forms for each side.  Thus `review_with` can explicitly use `effect:nitric_oxide_support` and `effect:pde5_inhibition`, while a class-like selector is never confused with a trait selector.

The scheduling-critical existing conflict is preserved precisely as a `competes` relation with `source_selector: {category: kind, term: mineral}` and `target_selector: {category: quality, term: fat_soluble}`.  Matching means: source substance has `knowledge.kind: mineral` and target substance has `knowledge.quality: fat_soluble`; it is directional only if the canonical relation declaration says so.  The relation matcher and `slot_is_blocked` consume this generic selector contract, so moving `fat_soluble` out of historical `is:` preserves the exact mineral-versus-fat-soluble conflict set.  Regression fixtures must assert the prior and post-cutover matched pairs and blocked slots are identical.  No false `kind` is retained for compatibility.

### 4.4 Runtime modules and interfaces

The final tree has one explicit replacement/removal map; a listed legacy module may not remain as a shim, re-export, fallback reader or second validator:

| Legacy owner | Canonical replacement | Final action |
|---|---|---|
| `data/traits/*.yaml` and `planner/cards/traits.py` | `ontology/{supp_slotter,vocabulary,relations,ontoclean}.yaml` and `planner/ontology/artifacts.py` | delete data registry and trait loader |
| `schema/{substance,product,relations,dashboard,stacks,pillboxes,traits}.schema.json` and `planner/schema_validation.py` semantic loading | `ontology/generated/schema/*` and `planner/ontology/validation.py` | delete handwritten semantic schemas/load path; retain only non-semantic parsing support that is still required |
| `planner/domain_constants.py` ontology namespaces/categories/term lists | generated `RuntimeVocabulary` | delete ontology constants; retain unrelated presentation constants only after a grep-audited split |
| `planner/cards/relations.py` legacy endpoint parser and `planner/query_model/relation_matches.py` legacy class/trait matching | typed-selector parser and matcher in `planner/ontology` | replace, then delete all legacy endpoint branches |
| `planner/cards/dashboard_validation.py` historical context rules | canonical dashboard/context contract plus SHACL | replace handwritten semantic checks; retain only transport/path diagnostics if needed |
| `planner/query_model/surreal_records.py` trait-registry load | canonical vocabulary/RDF-derived records | replace source; retain `mem://` navigation/audit role |

The removal commit includes a grep allowlist audit for `data/traits`, `REGISTERED_NAMESPACES`, `load_traits`, old `is_` semantic accessors, handwritten `*.schema.json` semantic loaders and legacy relation endpoint keys.  Every remaining match must be an explicitly named migration fixture or deletion test; otherwise it blocks cutover.

Create a new low-level `planner/ontology/` package.  It may be imported by `planner.cards`, `planner.schema_validation`, and `planner.query_model`, but it must not import engine commands, preserving the existing import-linter direction.

| File | Responsibility |
|---|---|
| `planner/ontology/artifacts.py` | Locate generated artifacts, verify source hash/schema version, load the generated runtime vocabulary. |
| `planner/ontology/model.py` | Typed immutable ontology term, predicate, relation-type and profile contracts. |
| `planner/ontology/cards.py` | Convert validated YAML card mappings to canonical RDF-facing facts without business logic. |
| `planner/ontology/rdf.py` | Deterministic RDFLib projection of ontology terms, substances, products, components, relations, stacks and dashboards. |
| `planner/ontology/validation.py` | Run generated structural validator and pySHACL; format deterministic, card-path-addressable errors. |
| `planner/ontology/generate.py` | Explicit generation command used by the repository script; writes only `ontology/generated/`. |
| `scripts/generate_ontology.py` | Thin typed CLI wrapper for deterministic generation and `--check` freshness mode. |
| `scripts/ontology_inventory.py` | Read-only migration accounting report: input/output IDs, field-level facts, predicate relocation and intentional drops. |

Public interfaces are deliberately narrow:

```python
def load_ontology(root: Path) -> Ontology: ...
def validate_ontology_artifacts(ontology_root: Path) -> list[OntologyError]: ...
def project_repository_to_rdf(paths: Paths, ontology: Ontology) -> Graph: ...
def validate_repository_ontology(paths: Paths, ontology: Ontology) -> list[OntologyError]: ...
def build_runtime_vocabulary(ontology: Ontology) -> RuntimeVocabulary: ...
```

`OntologyError` includes an artifact/card path, machine-readable rule ID, RDF focus node/predicate when available, and a short remediation.  Expected data violations return these errors.  Artifact loading, generation, RDF projection and pySHACL-engine failures raise a distinct `OntologyInfrastructureError`, caught only by the command boundary and reported as a non-zero fail-closed check failure; they must never be converted to an empty error list or a pass result.

`planner/engine/check.py` becomes the sole orchestration point: auto-maintenance remains first; artifact freshness/structural validation runs before loading cards; normal card identity/reference checks run on the generated model; RDF/SHACL runs on the whole loaded graph; all errors report through `planner.check_report.report`.  The old `load_traits`, `check_traits`, `REGISTERED_NAMESPACES` and handwritten semantic schemas are removed rather than kept as compatibility code.

`planner/contracts.py` may retain runtime data contracts needed by the scheduler, but their allowed namespace/predicate values come from `RuntimeVocabulary`, not hard-coded constants.  `planner/query_model/surreal_records.py` is updated to serialize canonical predicates (for example, `kind`, `role`, `quality`) and generated term labels.  Query-model behavior remains isolated behind `StackReadModel`; no SurrealQL should be introduced into validation.

Performance is an acceptance gate, not an aspiration: on the repository baseline (253 substance and 59 product cards), a warm `uv run python -m planner check` including RDF projection and pySHACL must complete in **under 5 seconds** on the CI-equivalent host; a cold clean-process run must complete in **under 10 seconds**.  `tests/test_ontology_performance.py` (or a dedicated `just ontology-benchmark` invoked in CI) measures and reports both budgets with enough tolerance only for documented CI variance; a regression beyond either bound blocks the cutover.

### 4.5 Generated artifacts and dependency policy

Add LinkML as a development/CI-only generator dependency; production runtime dependencies are RDFLib and pySHACL only.  Lock all of them with `uv` and pin only through the lock file under the repository's existing dependency-management policy.  Before accepting versions, run an explicit Python 3.14 spike using `uv sync --locked`, LinkML generation, `rdflib.Graph` construction and `pyshacl.validate` in the same CI-like interpreter.  The dependency is rejected if that exact environment cannot lock and execute deterministically.  Normal planner commands must not import LinkML or require its generator dependency.

Generation produces:

- JSON Schema used for card structural checks;
- OWL/Turtle ontology for interchange and human inspection;
- SHACL/Turtle shapes for closed-world constraints and graph-wide semantic checks;
- a compact YAML runtime vocabulary used for labels, placement rules, scheduling effects and relation metadata.

The committed output is reviewed like generated source.  `scripts/generate_ontology.py --check` regenerates to a temporary location or compares canonical bytes/hashes and fails if working-tree artifacts differ.  Runtime commands never generate artifacts implicitly and never write card data as a side effect of validation.

### 4.6 SHACL rule set

Generated shapes cover straightforward class/property/cardinality constraints.  SHACL-SPARQL constraints are limited to graph-wide rules that cannot be expressed structurally.  Initial mandatory rules:

1. a term has exactly one declared semantic category and valid OntoClean profile for that category;
2. every trait fact uses a registered term and only an allowed card predicate;
3. `kind` slots contain only rigid kinds; roles, qualities, effects, risks, pathways and contexts cannot appear there;
4. every scheduling term has valid scoring/block metadata and appears only in its declared scheduling predicate;
5. every product component resolves to exactly one `Substance` ID;
6. relation selectors exist, have one declared selector form, resolve to an entity or registered term as appropriate, and satisfy the relation type's per-side allowed entity/category policy;
7. symmetric relations cannot be duplicated or reversed-duplicated; self-relations are forbidden unless the relation type explicitly permits them;
8. every extensional context has a dashboard, and every dashboard selector references registered terms/predicates;
9. IDs, component ownership, and required label/provenance fields obey the generated model;
10. cards cannot carry ontology predicates unknown to the canonical vocabulary.

This validates declared semantics and contradictions in the repository graph.  It does not claim to prove biomedical truth, dose adequacy, or infer whether a term is a role from its English label.

### 4.7 Data preservation accounting

The **first implementation commit** on the feature branch creates the machine-readable baseline snapshot and the read-only accounting tool before any ontology or card data edit.  The snapshot lives under `tests/fixtures/ontology_migration/`, not mutable live data at test runtime, and captures counts and normalized facts for all substances, products, components, IDs, aliases, forms, notes, concerns, schedule facts, knowledge facts, relation selectors, dashboards and stacks.  This ordering is a merge gate: a baseline captured after a migration edit is invalid.

After migration, `scripts/ontology_inventory.py` compares baseline to canonical cards and emits a deterministic report with:

- all original and final `sub_*`/`prd_*` IDs and a one-to-one identity check;
- all product-to-substance component edges;
- normalized fact preservation status (`preserved`, `relocated`, `consolidated`, `intentional_drop`);
- exact source path, destination path and rationale for every relocated or intentionally dropped fact;
- a failure for an unaccounted missing useful fact, duplicate ID, dangling component or changed ID.

The report is an acceptance artifact and test oracle, not a runtime compatibility layer.  It may be removed only if its assertions are retained as committed tests and the migration accounting remains reproducible from fixtures.

## 5. Security Design

### Threat model

| Asset | Threat actor/vector | Mitigation |
|---|---|---|
| Canonical ontology and generated artifacts | Contributor edits generated output or stale artifacts bypass new rules | Source hash/version, deterministic `--check` generation in `just check` and CI, generated directory is never an authoring input. |
| Card integrity | Malformed YAML, unknown predicate, duplicate/reversed relation, dangling component | Generated JSON Schema plus RDF/SHACL validate before commands consume graph; errors fail closed. |
| Local filesystem | Path traversal/symlink input through generator or `data_root` fixture | Resolve configured repository-relative roots, reject paths outside the supplied root, do not follow generated output paths supplied by card data. |
| Availability | Oversized/recursive RDF graph or pathological SHACL-SPARQL query | Fixed local input set, deterministic bounded projections, no user-supplied queries, test a synthetic large/malformed input; document command time budget. |
| Private data | Diagnostics serialize raw private notes or logs | Projection includes only tracked ontology/card fields needed by shapes; errors use IDs/paths/rule IDs, never dump whole documents. |
| Supply chain | New Python dependency compromise/vulnerability | `uv.lock`, existing pinned CI setup, Dependabot/CodeQL posture, dependency review before lock update, no external ontology downloads at runtime. |

### Security controls checklist

- Input validation: generated structural schema validates types, patterns, cardinalities, closed properties and references; pySHACL validates graph-wide semantics.
- Output encoding: no HTML/SQL/shell output is introduced; diagnostics are plain text through existing reporting.
- Access control: not applicable to local CLI; no service/API/credentials are added.
- Filesystem: fixed repository paths and explicit `Paths` root; generator writes only under `ontology/generated/`.
- Secrets: none added, logged or read.
- Infrastructure: no server, network connection, container capability, mount, port or persistent database change.

## 6. Implementation Steps

### Step 0: Locked Python 3.14 dependency and representative performance precondition

**Files:** development/CI dependency group in `pyproject.toml`, `uv.lock`, a committed `tests/test_ontology_dependency_spike.py` and `tests/test_ontology_performance.py`; temporary throwaway spike files only where they are not part of the final test suite.

**Changes:** this is the first implementation commit and a hard branch precondition.  Select, lock and commit the exact LinkML (dev/CI only), RDFLib and pySHACL release set with `uv`; in the repository's supported Python 3.14 interpreter run `uv sync --locked`, generate a representative LinkML schema to JSON Schema/OWL/SHACL, construct the representative RDF graph, and run pySHACL.  The representative graph must contain at least the baseline-scale cardinalities (253 substances, 59 products, 282 components, 36 relations and 27 dashboards) or a generated equivalent with the same selector/property fan-out.  Measure both cold and warm validation against the 10-second and 5-second budgets.  Commit the selected lock and a reproducible test/benchmark invocation before creating ontology sources or editing any card.  Prove normal `planner check` has no LinkML import.  If exact locking, generation, validation, or either representative budget fails, stop the branch: do not begin ontology, schema, runtime or card work and do not substitute an untested version.

**Rationale:** Python 3.14 support and the semantic-validation performance envelope are feasibility gates, not work that can be deferred until after a migration.

### Step 1: Capture immutable migration baseline

**Files:** new `planner/ontology/migration_normalize.py`, new `scripts/ontology_inventory.py`, `tests/fixtures/ontology_migration/*`, `tests/test_ontology_normalize.py`, `tests/test_ontology_migration_accounting.py`.

**Changes:** after Step 0 and before any ontology/card/schema/runtime migration, commit and test the exact normalizer described in Section 4.1, then capture the approved pre-migration repository using the existing readers.  The immutable baseline fixture records `origin_commit`, `origin_tree`, capture command/version, normalizer version/hash and the approved pre-migration commit/tree.  CI verifies the recorded tree object equals `origin_commit^{tree}`, the recorded origin commit is an ancestor of (or equal to) the cutover commit under test, and it equals the approved pre-migration commit/tree named by the migration manifest; failure is fatal rather than advisory.  The inventory tool must reject a baseline whose provenance does not pass these checks, and tests must prove it detects a removed fact, changed `sub_*`/`prd_*` ID, dangling product component, changed relation selector, dashboard/context change and an unaccounted relocation.  Do not edit ontology sources, cards, relations, dashboards, schemas or runtime semantics before this commit is complete.

**Rationale:** accounting is credible only when its baseline predates every semantic and data transformation.

### Step 2: Establish authored ontology and deterministic artifacts

**Files:** new `ontology/manifest.yaml`, `ontology/supp_slotter.yaml`, `ontology/model.yaml`, `ontology/vocabulary.yaml`, `ontology/relations.yaml`, `ontology/ontoclean.yaml`, `ontology/constraints/semantic.ttl`, `ontology/migrations/v1-term-map.yaml`, `ontology/migrations/v1-relation-map.yaml`, `ontology/migrations/v1-dashboard-map.yaml`, `ontology/generated/*`, `scripts/generate_ontology.py`, new `planner/ontology/artifacts.py`, `planner/ontology/model.py`, `planner/ontology/generate.py`, `justfile`.

**Changes:** express the complete current card, term, dashboard and relation model in LinkML; set the exact base IRI from Section 4.2 consistently in every source/generator/template; make `manifest.yaml` own every authoring input, including custom SHACL-SPARQL; add OntoClean profiles and term placement policy; generate and commit artifacts; add `just ontology-generate` and `just ontology-check` (freshness plus loadability).  Inventory all 27 existing dashboard files/rules into `v1-dashboard-map.yaml`; each source dashboard/context fact or selector has exactly one canonical dashboard selector or an explicit intentional removal rationale, and the generated hard check rejects omitted, dangling or duplicate mappings.  Make `just check` depend on `ontology-check` before type checking/tests.  Commit the normative RDF identity/projection table as tests alongside `rdf.py`, not prose alone.

**Rationale:** this creates the only authoring root before moving consumers or data.

### Step 3: Implement canonical structural and semantic validation

**Files:** new `planner/ontology/cards.py`, `planner/ontology/rdf.py`, `planner/ontology/validation.py`; modify `planner/engine/check.py`, `planner/schema_validation.py`, `planner/paths.py`, `planner/contracts.py`; add `tests/test_ontology_artifacts.py`, `tests/test_ontology_validation.py`, fixture support in `tests/planner_fixture.py`.

**Changes:** replace direct handwritten-schema loading with generated artifact loading; project the fully loaded repository to RDFLib exactly as Section 4.2 specifies; execute generated and authored SHACL rules; return deterministic path/rule diagnostics through the current check report.  Keep existing card identity, normalization and product resolution responsibilities, but make them query canonical vocabulary rather than independent semantic constants.  A pySHACL, projection, loader, or artifact failure is an `OntologyInfrastructureError` and fails the command rather than appearing as a clean report.

**Rationale:** validation becomes executable and centralized without turning SurrealDB into a validator or changing command surface.

### Step 4: Migrate vocabulary and cards with accounting

**Files:** migrate `data/substances/*.yaml`, `data/products/*.yaml` only where required, `data/relations.yaml`, `data/dashboards/*.yaml`, templates under `schema/templates/` (or their generated replacement); new `scripts/ontology_inventory.py`, committed migration fixture/baseline and `tests/test_ontology_migration_accounting.py`.

**Changes:** map every existing trait to a declared canonical term; migrate cards to `kind`/`role`/`quality`/`effect`/`risk`/`pathway`/`context` as approved by the ontology package; migrate all relations to the generic typed selector model; retain all useful product/substance facts or explicitly account for their relocation/removal.  Preserve IDs and component edges.  Resolve each blend as reusable substance vs product-only label artifact with an entry in the report.  Add an explicit before/after regression fixture proving the `kind:mineral` × `quality:fat_soluble` `competes` match and its resulting slot blocks are unchanged.

The migration command reads the committed baseline and refuses to run unless both exhaustive maps have a one-to-one source-record inventory: every legacy relation record is consumed once, each of its actual endpoint keys is parsed by the explicitly selected legacy-shape adapter, and exactly one new typed relation is emitted.  It emits a source-record-to-target-record ledger (including stable source path/ID, old shape, selectors and relation type), which `tests/test_ontology_migration_accounting.py` compares as a multiset.  A relation whose endpoint is a name, explicit substance, trait, class, mixed legacy shape, or missing value cannot fall through to a generic resolver; it either maps according to its enumerated record or fails.  `v1-dashboard-map.yaml` is checked in the same run against the baseline dashboard/context inventory.

**Rationale:** this is the deliberate semantic migration; it must not hide data loss behind a schema conversion.

### Step 5: Move all runtime consumers and retain SurrealDB role

**Files:** modify `planner/cards/traits.py`, `planner/cards/substance_validation.py`, `planner/cards/relations.py`, `planner/cards/dashboard_validation.py`, `planner/domain_constants.py`, `planner/query_model/surreal.py`, `planner/query_model/surreal_records.py`, relevant `planner/engine/*`, `tests/test_traits_loading.py`, `tests/test_card_reference_integrity.py`, `tests/test_review_command.py`, `tests/test_audit_command.py`.

**Changes:** replace trait-directory loading and namespace constants with generated `RuntimeVocabulary`; rename runtime fields where required; make generic typed-selector relation resolution consult ontology metadata; update `slot_is_blocked` and all scheduling conflict matching to consume `kind` and `quality` selectors rather than historical `is_`; load canonical terms into SurrealDB records for navigation/audit.  Retain `Surreal("mem://")`, `StackReadModel`, existing graph queries and command-scoped population.

**Rationale:** all consumers must use the new source before legacy code is removed, while graph navigation and audit stay unchanged in architectural responsibility.

### Step 6: Remove legacy semantic sources and update documentation

**Files:** remove `data/traits/*.yaml`, obsolete `schema/*.schema.json`, obsolete trait schema templates and legacy semantic constants/validators; modify `README.md`, `docs/domain-model.md`, `docs/README.md`, `docs/agent-product-flow.md`, `schema/templates/*` or replacement `ontology/templates/*`, `.github/workflows/ci.yml` if an explicit artifact job is warranted.

**Changes:** delete all duplicate ontology source material after consumers and tests use artifacts.  Rewrite docs so they point to `ontology/supp_slotter.yaml` as the editable ontology root, explain generated outputs and semantic categories, and retain clear card-editing guidance.  Do not leave a prose rule or Python constant as an alternate source of truth.

**Rationale:** final cutover is real only if old sources cannot silently diverge.

### Step 7: Prove cutover and operational behaviour

**Files:** test additions/updates above, `justfile`, CI workflow only if needed.

**Changes:** run the accounting test, all semantic-negative tests, planner check, plan, review, audit and find against fixture and repository data; add explicit import-linter contracts: `planner.ontology` cannot import engine, query model, maintenance, or schedule writer; `planner.cards`, `planner.schema_validation`, and `planner.query_model` may depend downward on `planner.ontology`; `planner.ontology` is added to the acyclic feature-package contract.  Add an architecture test/grep guard that fails if legacy trait paths or handwritten semantic schema loaders are imported by runtime modules.  Run `just verify`, `just coverage-check`, `just crap-check`, `just ontology-check`, and CI-equivalent clean install.

**Rationale:** the branch is mergeable only when preservation, validation, no-dual-path and command behaviour are demonstrated together.

## 7. Test Plan

### 7.1 Unit tests

- `tests/test_ontology_artifacts.py`: root imports resolve; generated outputs are fresh, deterministic and source-hash matched; tampering/staleness fails closed.
- `tests/test_ontology_validation.py`: every initial SHACL rule has a focused valid and invalid fixture, with path/rule-ID diagnostics.  The minimum discriminating fixtures are: a role placed under `knowledge.kind`; a non-existent term URI; a `competes` relation whose `target_selector` falsely declares `kind:fat_soluble`; a selector with both entity and term forms; a reversed duplicate of a symmetric relation; a dashboard selector that refers to a removed term; and an extensional `knowledge.context` fact with no mapped dashboard.  Each fixture changes only the one fact needed to violate its target rule and has a paired minimal conforming graph.
- `tests/test_ontology_shacl_sparql.py`: a parameterized negative-fixture harness gives every authored SHACL-SPARQL rule an isolated violating graph, asserts non-conformance and rule ID, and pairs it with a minimal conforming graph.  A rule cannot be added to `constraints/semantic.ttl` without a registered fixture case.
- `tests/test_ontology_rdf.py`: canonical cards project deterministically to expected RDF triples; no private/unneeded data is projected.
- `tests/test_ontology_runtime_vocabulary.py`: runtime lookup returns labels, allowed predicates, scheduler effects and relation metadata exclusively from artifacts.
- `tests/test_ontology_migration_accounting.py`: provenance tree/commit checks, all baseline IDs, product-component edges, relation records/selectors, dashboard/context mappings and useful normalized facts are preserved, relocated with rationale, or intentionally dropped; unaccounted data loss fails.
- Update `tests/test_schemas.py`, `tests/test_traits_loading.py`, `tests/test_card_reference_integrity.py` to assert generated-schema/canonical-vocabulary behavior rather than legacy paths.

### 7.2 Integration tests

- `planner check` rejects each invalid semantic placement (for example a role under `knowledge.kind`) and exits non-zero without producing schedule output.
- `planner check` accepts migrated repository data and synthetic isolated fixture trees; tests must continue using `tests/planner_fixture.py`/copied data, not mutate live `data/`.
- Product resolution preserves `prd_* -> sub_*` component edges after migration.
- `planner`, `planner review`, `planner audit`, `planner audit --full`, `planner find`, and `planner review-substance` operate from the canonical vocabulary and retain expected user-visible results except intentional semantic relabeling.
- SurrealDB integration test proves one fresh `mem://` session receives canonical category data and supports audit/navigation; no persistent DB path is opened.
- Architecture test proves `planner.cards`, `planner.query_model` and engine consumers do not import `data/traits`, handwritten schemas or legacy registry functions.

### 7.3 Security and robustness tests

- malformed YAML, unknown predicates, extra fields, invalid ID patterns, oversized strings/lists within a controlled fixture, cyclic/self relation and reversed duplicate relation all fail deterministically;
- artifact source hash mismatch and manually edited generated file fail `ontology-check`;
- generator rejects an output path outside `ontology/generated/` and does not write cards;
- a fixture with dashboard/context mismatch and a fixture with an omitted baseline dashboard mapping each fail the hard dashboard-map/SHACL gate;
- the typed selector fixture proves `competes(kind:mineral, quality:fat_soluble)` resolves the expected substances and preserves the scheduling blocks from the migration baseline;
- a warm and cold `planner check` benchmark meet the 5-second and 10-second budgets respectively;
- error reports include rule/path but not full YAML/private-note content;
- dependency smoke test runs in a clean `uv sync --locked` environment under Python 3.14.

## 8. Rollback Strategy

No production database migration exists: YAML and artifacts are Git-tracked and SurrealDB is ephemeral.  The safe rollback is to revert the feature branch/merge commit as a unit, restoring prior cards, schemas, traits and runtime code together.  Do not attempt a partial rollback of generated artifacts or only the cards: that would recreate two semantic sources.

Before merge, keep the migration accounting report and commit sequence reviewable.  If a material data-preservation or semantic decision is disputed, stop before merge, amend the canonical ontology/card mapping on the feature branch, regenerate artifacts and re-run the full gate.  `main` remains untouched until the complete cutover passes.

## 9. Validation Commands

```bash
# Dependency spike and clean install (once dependencies are proposed)
uv sync --locked

# Regenerate only when authoring ontology changed; review generated diff
uv run python scripts/generate_ontology.py

# Must not write; fails on stale/malformed generated artifacts
uv run python scripts/generate_ontology.py --check

# Canonical project commands
uv run python -m planner check
uv run python -m planner
uv run python -m planner review
uv run python -m planner audit
uv run python -m planner audit --full
uv run python -m planner find "magnesium"

# Full repository quality gates
just check
just unit
just verify
just coverage-check
just crap-check
```

`just check` must include the non-writing artifact freshness gate.  `just unit` must include the canonical semantic validation invoked by `planner check`.

## 10. Documentation Updates

- `README.md`: retain the short YAML-first overview; state that ontology authoring lives in `ontology/supp_slotter.yaml`, artifacts are generated, and SurrealDB is an in-memory query/audit layer.
- `docs/domain-model.md`: replace semantic source-of-truth prose with a concise explanation of canonical categories, ownership boundaries, migration-aware card examples and links to the ontology root/generated docs.
- `docs/README.md`: add an Ontology Contract entry and route detailed authoring instructions there.
- `docs/agent-product-flow.md`: change trait-edit guidance to canonical ontology terms and generated schema validation; preserve product intake workflow.
- `ontology/README.md` (new, required): exact authoring/generation/check workflow, manifest ownership of LinkML plus authored SHACL-SPARQL, no hand edits to `generated/`, how to choose kind/role/quality/effect/risk/pathway/context, and how to add a term safely.
- Templates: point substance/product authors to canonical predicate names and generated schema; never duplicate the controlled vocabulary.

## 11. Validation Checklist

### Implementation

- [ ] Python 3.14 dependency spike passes before migration work is accepted.
- [ ] The committed lock, representative 253/59/282/36/27 spike and warm/cold performance budgets pass before ontology or card work begins.
- [ ] Baseline provenance records the approved pre-migration commit/tree and CI proves it mechanically.
- [ ] LinkML root and imported modules contain every ontology decision.
- [ ] Generated JSON Schema, OWL, SHACL and runtime vocabulary are deterministic and fresh.
- [ ] All useful substance/product facts are preserved or explicitly accounted for.
- [ ] All stable `sub_*` and `prd_*` IDs and product-component references are preserved.
- [ ] Ambiguous existing terms and blends have explicit decisions recorded in the canonical ontology/accounting report.
- [ ] `planner check` has one canonical validation path with no fallback.
- [ ] LinkML is used only by deterministic dev/CI generation; normal runtime imports only generated artifacts plus RDFLib/pySHACL.
- [ ] Planner/review/audit/find read the generated runtime vocabulary.
- [ ] SurrealDB remains command-scoped `mem://` navigation/audit infrastructure.
- [ ] `data/traits`, handwritten semantic schemas/constants and legacy registry code are removed.
- [ ] Tests use synthetic/copied fixture data, not mutable live card data.
- [ ] `just verify`, coverage and CRAP gates pass.
- [ ] Warm and cold `planner check` meet the 5-second and 10-second performance budgets.
- [ ] CI clean install and workflow pass.
- [ ] Documentation points to one editable ontology source.

### Security

- [ ] Artifact tampering/staleness fails closed.
- [ ] Malformed/unknown/semantically misplaced card facts fail closed.
- [ ] Generator cannot write outside `ontology/generated/`.
- [ ] No network service, credentials, persistent ontology database or new elevated permission is introduced.
- [ ] Diagnostics do not expose private/full card content unnecessarily.
- [ ] New dependency lockfile and Python 3.14 execution are reviewed.
- [ ] No CRITICAL/HIGH security issue is introduced by the new dependency set.
