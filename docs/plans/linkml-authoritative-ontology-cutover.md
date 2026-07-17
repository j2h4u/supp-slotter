# LinkML-First Ontology Cutover

## Goal and boundaries

Make one modular LinkML schema graph plus declarative instance catalogs the sole authored/domain source of truth. Generate RDF, SHACL, JSON Schema, OWL, a runtime vocabulary, and a projection map from it. `planner check` projects the entire repository to RDF and runs SHACL; Python retains only generic IO, graph traversal/projection, rule interpretation, deterministic search/backtracking, rendering, serialization, and CLI orchestration.

Non-goals: dose calculation, diagnosis, clinical knowledge graphs, or adoption of an external ontology. Existing `sub_*`/`prd_*` IDs, cards, components, and user behavior are preserved; provenance/evidence is never a correctness oracle. This is feature-branch construction only: no flags, fallback, dual active paths, or compatibility shim.

## Decision

LinkML-first was selected over RDF-first (excellent interchange, but weak authoring ergonomics and closed-world validation) and YAML plus Python (familiar, but recreates scattered semantic rules and hidden branches). LinkML gives a reviewable model and deterministic generators; RDFLib/pySHACL provide the runtime graph gate without importing LinkML/compiler.

## Target package, manifest, and generated artifacts

`ontology/manifest.yaml` is the only authored root and explicitly enumerates every schema module, vocabulary/catalog file, custom SHACL constraint, and pinned generator/tool identity and version. Every path is normalized relative to one repository-root-contained base; absolute paths, parent escapes, implicit globs, undeclared inputs, and derived digests in the manifest are errors. `ontology/generated/artifact-lock.json` alone owns computed canonical source digests and generated output digests, plus schema/tool versions and generation metadata. Generated outputs (RDF/OWL, SHACL, JSON Schema, JSON-LD context, runtime vocabulary, projection map) are committed, reproducible, and never hand-edited.

Generation and LinkML dependencies are dev/CI-only. Runtime freshness is pure hash/IO over the manifest and artifact lock and never imports or calls LinkML, generators, or `SchemaView`; a cold runtime and CLI mutation path must prove this. All consumers, including relations, use one `load_ontology()` and its generated projection path. `project_repository_to_rdf()` covers the full corpus, not only touched records. SurrealDB remains an ephemeral `mem://` navigation/audit read model.

## Semantic ownership and leakage removal

Declarative data owns score magnitudes, category-to-axis mappings, selector dispatch, warning labels, display filtering/order, authority, evidence state, and relation interpretation. Python owns only arithmetic/matching/traversal/search/serialization/render mechanics. The projection map owns category-to-field dispatch; unknown categories fail closed.

Remove semantic leakage: `LEVEL_SCORES`, `SECONDARY_TRAIT_WEIGHT`, `BALANCE_WEIGHT`, `PREFER_WITH_BONUS`, `WARNING_CATEGORY_LABELS`, prefix filtering, `NAMESPACE_ORDER`, `substance_carries`, direct relation loaders, legacy accessors, and registry names. Intake, timing, and activity are axes under `schedule_rule`, never semantic categories. Static AST/import/direct-read guards reject legacy registries, `REGISTERED_NAMESPACES`, old `is_` accessors, handwritten catalogs, and LinkML imports in runtime modules.

## Evidence governance and normalized traces

Every migrated term, relation, dashboard selector, and card fact has a deterministic source key, target key, rationale, reviewer, authority, and evidence state. `review_pending` and retired claims are inert: they cannot score, block, or influence ranking until explicitly approved. Preserve every fact or record an intentional drop/relocation; never infer semantics from labels.

Every decision emits a byte-identical normalized trace containing input/artifact digest, selectors, rules/source keys, exclusions with rule IDs, per-rule deltas, an ordered tie-break chain, and final score/result. Independent generic recomputation gates are mandatory for decision paths (not cosmetic snapshot tests).

## SHACL gate

`planner check` projects the complete repository and runs real RDF projection plus SHACL. Include a full-catalog sentinel fixture. Mutation in every rule family (registered term/category/profile, placement, schedule metadata, component resolution, typed selector, duplicate/reversed/self relation, dashboard/context, direction/cardinality, evidence state) must fail this real planner check. Rule IDs are stable. Validation failures and infrastructure failures are distinguished in diagnostics, but both fail closed.

## Strict migration sequence and gates

One path owner at a time; each gate blocks the next. Waves are strict and describe construction only:

1. **A — baseline/feasibility:** lock Python 3.14 dev dependencies; prove generation and RDFLib/pySHACL feasibility; record named CI-equivalent cold/warm measurements as explicit baseline results, without requiring the disposable pre-cutover implementation to meet final budgets. Freeze Git-bound normalized accounting for stable IDs, product-component edges, facts, relations, policies, and current behavior/layout. If complete normalized decision traces are unavailable pre-cutover, record that fact and bind a reconstructible surrogate oracle containing chosen assignments, layout provenance, and every currently exposed score, block, diagnostic, objective, and tie datum. Gate: complete reproducible frozen accounting and baseline tree verification before B.
2. **B — authored graph/artifacts:** author manifest, modules/catalogs, rule IDs, deterministic generators, artifact lock, path containment, and projection golden tests. Every SHACL rule family has paired positive and negative fixtures. Gate: deterministic source/output hashes, schema version, and fixture coverage.
3. **C — generic runtime enforcement:** implement `load_ontology()`, full-corpus RDF projection, SHACL runner, freshness/hash IO, fail-closed validation/infrastructure handling, and cold no-LinkML runtime/CLI mutation tests. Record the current clean `--no-dev` failure/import chain as a Wave C starting defect, never an accepted surviving xfail. Every SHACL rule family retains paired positive and negative fixtures; each negative mutation must fail the real `planner check` through projection/SHACL. Gate: all such failures, the starting defect resolved, and no generator/SchemaView imports.
4. **D — declarative migration:** migrate cards/substances/products, relations/assertions, dashboards, stacks, pillboxes, scheduling policies/constraints, authority, evidence, weights/objectives, presentation metadata, and audit rules with an exhaustive multiset ledger. Preserve IDs/components; pending and retired claims are behaviorally inert. Gate: full-corpus SHACL, no unaccounted facts, and exactly one relation interpretation path.
5. **E — consumer cutover:** update planner, scheduler, review/audit/find, and Surreal loaders to generated projection; remove all listed constants/loaders and legacy accessors. The first complete normalized decision trace and independent replay are delivered here. Gate: AST/import/direct-read guards, end-to-end regression traces with independent recomputation, measured cold <=10-second and warm <=5-second budgets on the named CI-equivalent profile, no dual path, and one consumer path per fact.
6. **F — atomic release/package/docs:** remove obsolete schemas/traits, document the single authoring root and generation workflow, run clean install/full gates (`just verify`, coverage/CRAP, package/runtime smoke, artifact/path checks), and reverify cold `planner check` <=10 seconds and warm <=5 seconds on the named CI-equivalent profile. Only Wave F may deploy.

No wave commits deploy. Feature lands as one squash/merge commit; rollback is revert of that merge commit. Do not add flags, fallback, or dual active paths.

## Final obligations and definition of done

The artifact lock is fresh and reviewable; a cold package/runtime works with no LinkML; every fact has exactly one consumer path; full-corpus SHACL is end-to-end mandatory; decision traces recompute independently and byte-identically; no implicit sources or hidden causes remain. Done means the manifest/catalogs are the sole authored ontology, all baseline facts/IDs/components are preserved or intentionally accounted for, pending/retired claims are inert, and all mutation, integration, static, performance, packaging, and CI gates pass.
