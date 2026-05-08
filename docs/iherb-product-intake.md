# iHerb Product Intake

This document is the staging area for iHerb products before they become product
and substance cards.

Purpose:

- keep the incoming product list in one place;
- deduplicate repeated links before writing YAML;
- extract label facts gradually and mark source confidence;
- use the batch as a stress test for product/substance modeling;
- add all resulting products to `inactive`, not to active stacks.

Do not treat URL slugs as label facts. A slug is only a starting hint until the
product page, label image, or another reliable source confirms brand, product
name, serving size, and components.

## Intake Rules

- Every product from this document starts as `inactive`.
- Ingestible supplements, fiber/food blends, and OTC/drug-like products are all
  in scope; the model cares about stack interactions, not legal product class.
- Product cards should keep the iHerb URL in `urls`.
- Create concrete substance/form cards when the label exposes a distinct form.
- Reuse existing substance cards only when the molecule/form matches.
- Do not invent ingredient forms, amounts, or relations from product marketing
  text alone.
- If the product page is discontinued or blocked, record that in notes and use
  only facts visible from reliable sources.
- Preserve user-supplied hints such as `(pre_workout)`.

## Duplicates

The submitted list contains these duplicate URLs:

- https://www.iherb.com/pr/natural-factors-biocoenzymated-active-b-complex-60-vegetarian-capsules/85648
- https://www.iherb.com/pr/now-foods-potassium-citrate-99-mg-180-veg-capsules/13061
- https://www.iherb.com/pr/country-life-core-daily-1-multivitamin-for-women-60-tablets/34145
- https://www.iherb.com/pr/nature-s-way-alive-calcium-max-absorption-120-tablets/43056

## Unique Products

| # | URL | Slug hint | User hint | Intake status |
|---|---|---|---|---|
| 1 | https://kz.iherb.com/pr/jarrow-formulas-toco-sorb-60-softgels/137 | Jarrow Formulas Toco-Sorb, 60 softgels | inactive | YAML card added |
| 2 | https://kz.iherb.com/pr/now-foods-buffered-c-1000-complex-90-tablets/117137 | NOW Foods Buffered C-1000 Complex, 90 tablets | inactive | YAML card added |
| 3 | https://kz.iherb.com/pr/california-gold-nutrition-nicotinamide-riboside-tartrate-nrt-complex-60-veggie-capsules/146469 | California Gold Nutrition Nicotinamide Riboside Tartrate NRT Complex, 60 veggie capsules | inactive | YAML card added |
| 4 | https://www.iherb.com/pr/swanson-tocotrienols-100-mg-60-liquid-caps/118598 | Swanson Tocotrienols, 100 mg, 60 liquid caps | inactive | YAML card added |
| 5 | https://www.iherb.com/pr/life-extension-vitamins-d-and-k-with-sea-iodine-60-capsules/78779 | Life Extension Vitamins D and K with Sea-Iodine, 60 capsules | inactive | intake facts staged |
| 6 | https://www.iherb.com/pr/natural-factors-astaxanthin-plus-4-mg-60-softgels/101667 | Natural Factors Astaxanthin Plus, 4 mg, 60 softgels | inactive | YAML card added |
| 7 | https://www.iherb.com/pr/jarrow-formulas-maculapf-carotenoid-complex-60-softgels-discontinued-item/99886 | Jarrow Formulas MaculaPF Carotenoid Complex, 60 softgels, discontinued item | inactive | YAML card added |
| 8 | https://www.iherb.com/pr/swanson-100-pure-krill-oil-60-softgels/109010 | Swanson 100% Pure Krill Oil, 60 softgels | inactive | YAML card added |
| 9 | https://www.iherb.com/pr/natural-factors-benfotiamine-30-vegetarian-capsules-165-mg-per-capsule/85656 | Natural Factors Benfotiamine, 30 vegetarian capsules, 165 mg per capsule | inactive | YAML card added |
| 10 | https://www.iherb.com/pr/life-extension-adrenal-energy-formula-120-vegetarian-capsules/87138 | Life Extension Adrenal Energy Formula, 120 vegetarian capsules | inactive | intake facts staged |
| 11 | https://www.iherb.com/pr/real-mushrooms-lion-s-mane-mushroom-extract-powder-120-capsules/112246 | Real Mushrooms Lion's Mane Mushroom Extract Powder, 120 capsules | inactive | intake facts staged |
| 12 | https://www.iherb.com/pr/the-genius-brand-pre-caffeine-free-blue-raspberry-10-5-oz-298-g/115936 | The Genius Brand Pre, caffeine free, blue raspberry, 10.5 oz / 298 g | inactive; pre_workout | intake facts staged |
| 13 | https://www.iherb.com/pr/now-foods-l-optizinc-100-veg-capsules/738 | NOW Foods L-OptiZinc, 100 veg capsules | inactive | YAML card added |
| 14 | https://www.iherb.com/pr/solaray-zinc-copper-with-kelp-pumpkin-seed-100-vegcaps/19000 | Solaray Zinc Copper with Kelp & Pumpkin Seed, 100 vegcaps | inactive | YAML card added |
| 15 | https://www.iherb.com/pr/doctor-s-best-stabilized-r-lipoic-acid-100-mg-180-veggie-caps/23168 | Doctor's Best Stabilized R-Lipoic Acid, 100 mg, 180 veggie caps | inactive | YAML card added |
| 16 | https://www.iherb.com/pr/natural-factors-biocoenzymated-active-b-complex-60-vegetarian-capsules/85648 | Natural Factors BioCoenzymated Active B Complex, 60 vegetarian capsules | inactive | intake facts staged |
| 17 | https://www.iherb.com/pr/doctor-s-best-nac-detox-regulators-180-veggie-caps/95570 | Doctor's Best NAC Detox Regulators, 180 veggie caps | inactive | intake facts staged |
| 18 | https://www.iherb.com/pr/now-foods-potassium-citrate-99-mg-180-veg-capsules/13061 | NOW Foods Potassium Citrate, 99 mg, 180 veg capsules | inactive | intake facts staged |
| 19 | https://www.iherb.com/pr/life-extension-mega-benfotiamine-250-mg-120-vegetarian-capsules/13192 | Life Extension Mega Benfotiamine, 250 mg, 120 vegetarian capsules | inactive | YAML card added |
| 20 | https://www.iherb.com/pr/now-foods-magnesium-glycinate-180-tablets-100-mg-per-tablet/88819 | NOW Foods Magnesium Glycinate, 180 tablets, 100 mg per tablet | inactive | YAML card added |
| 21 | https://www.iherb.com/pr/garden-of-life-super-seed-beyond-fiber-21-oz-600-g/3163 | Garden of Life Super Seed Beyond Fiber, 21 oz / 600 g | inactive | intake facts staged |
| 22 | https://www.iherb.com/pr/paradise-herbs-african-mango-extract-150-mg-60-vegetarian-capsules/51625 | Paradise Herbs African Mango Extract, 150 mg, 60 vegetarian capsules | inactive | intake facts staged |
| 23 | https://www.iherb.com/pr/swanson-full-spectrum-african-mango-400-mg-60-capsules/117790 | Swanson Full Spectrum African Mango, 400 mg, 60 capsules | inactive | intake facts staged |
| 24 | https://www.iherb.com/pr/source-naturals-ultra-mag-120-tablets/1415 | Source Naturals Ultra-Mag, 120 tablets | inactive | YAML card added |
| 25 | https://www.iherb.com/pr/solgar-skin-nails-hair-advanced-msm-formula-120-tablets/22419 | Solgar Skin, Nails & Hair Advanced MSM Formula, 120 tablets | inactive | intake facts staged |
| 26 | https://www.iherb.com/pr/source-naturals-calcium-hydroxyapatite-120-capsules/55874 | Source Naturals Calcium Hydroxyapatite, 120 capsules | inactive | YAML card added |
| 27 | https://www.iherb.com/pr/universal-u-daily-formula-the-everyday-multi-vitamin-100-tablets-discontinued-item/41356 | Universal U Daily Formula The Everyday Multi-Vitamin, 100 tablets, discontinued item | inactive | intake facts staged |
| 28 | https://www.iherb.com/pr/allmax-essentials-caffeine-200-mg-100-tablets/67652 | ALLMAX Essentials Caffeine, 200 mg, 100 tablets | inactive | intake facts staged |
| 29 | https://www.iherb.com/pr/ready-in-case-aspirin-81-mg-300-enteric-coated-tablets/38964 | Ready In Case Aspirin, 81 mg, 300 enteric coated tablets | inactive | intake facts staged |
| 30 | https://www.iherb.com/pr/controlled-labs-orange-triad-multi-vitamin-joint-digestion-immune-formula-270-tablets/24674 | Controlled Labs Orange Triad Multi-Vitamin Joint Digestion Immune Formula, 270 tablets | inactive | intake facts staged |
| 31 | https://www.iherb.com/pr/source-naturals-advanced-ferrochel-180-tablets/1021 | Source Naturals Advanced Ferrochel, 180 tablets | inactive | YAML card added |
| 32 | https://www.iherb.com/pr/source-naturals-male-response-90-tablets/1272 | Source Naturals Male Response, 90 tablets | inactive | intake facts staged |
| 33 | https://www.iherb.com/pr/optimum-nutrition-opti-men-multivitamin-for-active-men-150-tablets/57069 | Optimum Nutrition Opti-Men Multivitamin for Active Men, 150 tablets | inactive | intake facts staged |
| 34 | https://www.iherb.com/pr/natrol-melatonin-calm-sleep-fast-dissolve-strawberry-60-tablets-discontinued-item/36898 | Natrol Melatonin Calm Sleep Fast Dissolve, strawberry, 60 tablets, discontinued item | inactive | intake facts staged |
| 35 | https://www.iherb.com/pr/country-life-core-daily-1-multivitamin-for-women-60-tablets/34145 | Country Life Core Daily-1 Multivitamin for Women, 60 tablets | inactive | intake facts staged |
| 36 | https://www.iherb.com/pr/nature-s-way-alive-calcium-max-absorption-120-tablets/43056 | Nature's Way Alive Calcium Max Absorption, 120 tablets | inactive | YAML card added |
| 37 | https://www.iherb.com/pr/natural-balance-happy-sleeper-60-vegcaps/33841 | Natural Balance Happy Sleeper, 60 vegcaps | inactive | intake facts staged |
| 38 | https://www.iherb.com/pr/source-naturals-dmae-351-mg-200-tablets/1206 | Source Naturals DMAE, 351 mg, 200 tablets | inactive | intake facts staged |
| 39 | https://kz.iherb.com/pr/life-extension-melatonin-300-mcg-100-vegetarian-capsules/47809 | Life Extension Melatonin, 300 mcg, 100 vegetarian capsules | inactive | intake facts staged |
| 40 | https://kz.iherb.com/pr/animal-flex-comprehensive-joint-care-44-pill-packs/27238 | Animal Flex Comprehensive Joint Care, 44 pill packs | inactive | intake facts staged |

## Extracted Facts

### 1. Jarrow Formulas Toco-Sorb

Source:

- iHerb URL: https://kz.iherb.com/pr/jarrow-formulas-toco-sorb-60-softgels/137
- Official brand page: https://jarrow.com/products/toco-sorb-60-softgels

Extraction status: official brand page found via Exa; iHerb direct fetch is
blocked by Cloudflare.

Label facts:

- Brand: Jarrow Formulas
- Product name: Toco-Sorb
- Package: 60 softgels
- Serving size: 1 softgel
- Vitamin E as d-alpha tocopherol: 13 mg
- Tocotrienol-tocopherol complex: 375 mg
- Tocotrienols: 57 mg
- Tocotrienol forms listed: d-alpha, d-beta, d-gamma, d-delta
- Other ingredients: palm oil; softgel made from bovine gelatin, glycerin, and
  water; polyoxyl castor oil
- Suggested use: 1 softgel 1-2 times a day with a meal

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin E, form `d-alpha tocopherol`
  - Vitamin E, form `mixed tocotrienols`
  - possible product-level component label: `Tocotrienol-Tocopherol Complex`
- This is a good ontology test because the label has a broad complex and named
  concrete vitamin E forms.

### 2. NOW Foods Buffered C-1000 Complex

Source:

- iHerb URL: https://kz.iherb.com/pr/now-foods-buffered-c-1000-complex-90-tablets/117137
- Official brand page: https://www.nowfoods.com/products/supplements/vitamin-c-1000-complex-buffered-tablets

Extraction status: official NOW Foods page found via Exa.

Label facts:

- Brand: NOW Foods
- Product name: Vitamin C-1000 Complex, Buffered Tablets
- Package: 90 tablets
- Serving size: 1 tablet
- Vitamin C from calcium ascorbate: 1 g / 1,000 mg
- Calcium from calcium ascorbate: 100 mg
- Citrus bioflavonoid complex: 250 mg
- Acerola powder: 50 mg
- Rutin powder from Sophora japonica flower bud: 50 mg
- Suggested use from secondary retailer: 1 tablet daily

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin C, form `calcium ascorbate`
  - Calcium, form `calcium ascorbate`
  - Citrus bioflavonoid complex
  - Acerola powder
  - Rutin, plant source `Sophora japonica flower bud`
- This tests whether mineral salts should be represented as both the vitamin
  form and the mineral contribution, or as one product component plus label note.

### 3. California Gold Nutrition Nicotinamide Riboside Tartrate Complex

Source:

- iHerb URL: https://kz.iherb.com/pr/california-gold-nutrition-nicotinamide-riboside-tartrate-nrt-complex-60-veggie-capsules/146469
- Official brand page: https://www.californiagoldnutrition.com/products/california-gold-nutrition-nicotinamide-riboside-tartrate-nrt-complex-60-veggie-capsules-146469

Extraction status: official California Gold Nutrition page found via Exa.

Label facts:

- Brand: California Gold Nutrition
- Product name: Nicotinamide Riboside Tartrate (NRT) Complex
- Package: 60 veggie capsules
- Serving size: 1 capsule
- Nicotinamide riboside tartrate: 250 mg
- Coenzyme Q10 as ubiquinone: 100 mg
- Pyrroloquinoline quinone disodium salt (PQQ): 20 mg
- L-Ergothioneine: 5 mg
- Suggested use: 1 capsule daily, with food
- Other ingredients: modified cellulose veggie capsule, rice flour, magnesium
  stearate

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Nicotinamide riboside, form `tartrate`
  - Coenzyme Q10, form `ubiquinone`
  - Pyrroloquinoline quinone, form `disodium salt`
  - L-Ergothioneine
- This tests NAD precursor naming and whether `NRT` should be an alias for the
  tartrate form, not a separate generic substance.

### 4. Swanson Tocotrienols

Source:

- iHerb URL: https://www.iherb.com/pr/swanson-tocotrienols-100-mg-60-liquid-caps/118598
- Official brand page: https://www.swansonvitamins.com/p/swanson-ultra-double-strength-tocotrienols-100-mg-60-liq-caps

Extraction status: official Swanson page found via Exa.

Label facts:

- Brand: Swanson
- Product name: Tocotrienols - Double Strength
- Package: 60 liquid capsules
- Serving size: 1 liquid capsule
- Tocotrienol from DeltaGOLD tocotrienol: 100 mg
- Delta-tocotrienol: minimum 84%
- Gamma-tocotrienol: minimum 8%
- Other ingredients: rice bran oil, gelatin
- Suggested use: 1 liquid capsule per day with food and water

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin E, form `delta-tocotrienol`
  - Vitamin E, form `gamma-tocotrienol`
  - possible product-level component label: `DeltaGOLD tocotrienol`
- This is more concrete than a generic mixed tocotrienol card and may require a
  decision on whether percentages justify separate substance components.

### 5. Life Extension Vitamins D and K with Sea-Iodine

Source:

- iHerb URL: https://www.iherb.com/pr/life-extension-vitamins-d-and-k-with-sea-iodine-60-capsules/78779
- Official brand page: https://www.lifeextension.com/vitamins-supplements/item02040/vitamins-d-and-k-with-sea-iodine

Extraction status: official Life Extension page found via Exa.

Label facts:

- Brand: Life Extension
- Product name: Vitamins D and K with Sea-Iodine
- Package: 60 capsules
- Serving size: 1 capsule
- Vitamin D3 as cholecalciferol: 125 mcg / 5,000 IU
- Vitamin K activity: 2,100 mcg total
- Vitamin K1 as phytonadione: 1,000 mcg
- Vitamin K2 as menaquinone-4: 1,000 mcg
- Vitamin K2 as trans menaquinone-7: 100 mcg
- Iodine from Sea-Iodine Complex Blend: 1,000 mcg
- Iodine source blend: organic kelp and bladderwrack extracts, potassium iodide
- Suggested use: 1 capsule daily with food

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin D3, form `cholecalciferol`
  - Vitamin K1, form `phytonadione`
  - Vitamin K2, form `menaquinone-4`
  - Vitamin K2, form `trans menaquinone-7`
  - Iodine, possibly form/source `Sea-Iodine Complex`
- This tests K-vitamin form splitting and iodine source modeling.

### 6. Natural Factors Astaxanthin Plus

Source:

- iHerb URL: https://www.iherb.com/pr/natural-factors-astaxanthin-plus-4-mg-60-softgels/101667
- Official brand page: https://naturalfactors.com/products/astaxanthin-plus

Extraction status: official Natural Factors page found via Exa.

Label facts:

- Brand: Natural Factors
- Product name: Astaxanthin Plus
- Package: 60 softgels
- Serving size: 1 softgel
- Astaxanthin from Haematococcus pluvialis whole: 4 mg
- Lutein from Tagetes erecta / marigold flower: 1 mg
- Zeaxanthin from Tagetes erecta / marigold flower: 170 mcg
- Other ingredients: softgel with gelatin, glycerin, purified water; organic
  flaxseed oil
- Suggested use: 1 softgel per day

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Astaxanthin, source `Haematococcus pluvialis`
  - Lutein, source `Tagetes erecta / marigold flower`
  - Zeaxanthin, source `Tagetes erecta / marigold flower`
- This overlaps with MaculaPF and should reuse the same carotenoid substance
  cards where form/source matches.

### 7. Jarrow Formulas MaculaPF

Source:

- iHerb URL: https://www.iherb.com/pr/jarrow-formulas-maculapf-carotenoid-complex-60-softgels-discontinued-item/99886
- User-provided Supplement Facts text in chat, 2026-05-08
- User-provided product description text in chat, 2026-05-08
- Secondary source: https://www.allstarhealth.com/f/jarrow-maculapf.htm
- Secondary source: https://www.pasioonline.com/macula-protective-factors-60-softgels-lutein-astaxanthin-and-zeaxanthin-jarrow-formulas/

Extraction status: discontinued product; official current brand page not found
in this pass. User-provided Supplement Facts text is the strongest source and
matches several secondary retailers. User-provided product description differs
from Supplement Facts on meso-zeaxanthin amount.

Label facts:

- Brand: Jarrow Formulas
- Product name: MaculaPF / Macula Protective Factors
- Package: 60 softgels on iHerb/secondary discontinued listings
- Serving size: 1 softgel
- Choline from sunflower lecithin: 10 mg
- Lutein from marigold petal extract / Tagetes erecta: 20 mg
- Zeaxanthin from marigold petal extract / Tagetes erecta: 13 mg
- Meso-zeaxanthin: 9 mg
- RR-zeaxanthin: 4 mg
- Astaxanthin from Haematococcus pluvialis: 4 mg
- Other ingredients reported: sunflower lecithin; bovine gelatin softgel with
  water/glycerin/caramel; avocado oil; sunflower oil
- Suggested use: 1 softgel per day with food

Modeling notes:

- Product should become `inactive`.
- Prefer the Supplement Facts panel over product description text. The product
  description says `10 mg meso-zeaxanthin`, while Supplement Facts says `9 mg
  meso-zeaxanthin` and `4 mg RR-zeaxanthin`.
- Likely substance cards to review/create:
  - Choline, source `sunflower lecithin`
  - Lutein, source `Tagetes erecta / marigold petal extract`
  - Zeaxanthin, source `Tagetes erecta / marigold petal extract`
  - Zeaxanthin, form `meso-zeaxanthin`
  - Zeaxanthin, form `RR-zeaxanthin`
  - Astaxanthin, source `Haematococcus pluvialis`
- This tests whether stereoisomers such as meso-zeaxanthin and RR-zeaxanthin are
  separate substance forms.

### 8. Swanson 100% Pure Krill Oil

Source:

- iHerb URL: https://www.iherb.com/pr/swanson-100-pure-krill-oil-60-softgels/109010
- Official brand page: https://www.swansonvitamins.com/p/swanson-efas-pure-krill-oil-500-mg-60-sgels

Extraction status: official Swanson page found via Exa.

Label facts:

- Brand: Swanson
- Product name: 100% Pure Krill Oil
- Package: 60 softgels
- Serving size: 1 softgel
- Superba2 krill oil from shellfish: 500 mg
- Phosphatidylcholine (PC + LPC): 150 mg
- Omega-3 fatty acids: 110 mg
- EPA / eicosapentaenoic acid: 60 mg
- DHA / docosahexaenoic acid: 27.5 mg
- Astaxanthin from krill oil: 50 mcg
- Other ingredients: softgel with gelatin, glycerin, sorbitol, purified water,
  ethyl vanillin
- Allergen: contains shellfish / krill
- Suggested use: 1 softgel 1-2 times per day with meals and water; official page
  notes up to 4 times per day for additional benefits

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Krill oil, form/source `Superba2`
  - Phosphatidylcholine
  - EPA, krill/phospholipid context in product component notes
  - DHA, krill/phospholipid context in product component notes
  - Astaxanthin, source `krill oil`
- This overlaps with the existing krill/EPA/DHA model and tests whether delivery
  form should stay product-level instead of creating separate EPA/DHA substances.

### 9. Natural Factors Benfotiamine

Source:

- iHerb URL: https://www.iherb.com/pr/natural-factors-benfotiamine-30-vegetarian-capsules-165-mg-per-capsule/85656
- iHerb indexed page via Exa
- Related official page: https://naturalfactors.com/products/biocoenzymated-vitamin-b1-benfotiamine

Extraction status: iHerb indexed page provides the matching 165 mg per capsule
product. Official Natural Factors page appears to describe a related
benfotiamine plus sulbutiamine product, so do not merge facts blindly.

Label facts:

- Brand: Natural Factors
- Product name: Benfotiamine
- Package: 30 vegetarian capsules
- Serving size: 2 capsules
- Servings per container: 15
- Benfotiamine: 330 mg per 2 capsules
- Implied amount: 165 mg per capsule
- Suggested use: 1-2 capsules per day
- Other ingredients from iHerb indexed page: microcrystalline cellulose,
  vegetarian capsule with hypromellose and purified water, magnesium stearate,
  stearic acid, silica

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin B1, form `benfotiamine`
- Do not add sulbutiamine from the related official page unless the exact iHerb
  product label confirms it.

### 10. Life Extension Adrenal Energy Formula

Source:

- iHerb URL: https://www.iherb.com/pr/life-extension-adrenal-energy-formula-120-vegetarian-capsules/87138
- Official brand page: https://www.lifeextension.com/vitamins-supplements/item01630c/adrenal-energy-formula-c

Extraction status: official Life Extension page found via Exa.

Label facts:

- Brand: Life Extension
- Product name: Adrenal Energy Formula
- Package: 120 vegetarian capsules
- Serving size: 2 vegetarian capsules
- Servings per container: 60
- OciBest Holy Basil extract 10:1, whole plant, standardized to 2.5% triterpene
  acids: 600 mg
- Proprietary blend: 516 mg total
- Proprietary blend components:
  - Sensoril Ashwagandha extract 5:1, root and leaves, standardized to 32%
    oligosaccharides and 10% withanolide glycoside conjugates
  - Cordyceps / Paecilomyces hepiali extract 8:1, mycelia, standardized to 7%
    cordycepic acid
  - BaCognize Ultra Bacopa extract 25:1, whole herb, standardized to 25% bacopa
    glycosides
- Other ingredients: vegetable cellulose capsule, microcrystalline cellulose,
  maltodextrin, stearic acid, silica
- Suggested use: 2 capsules twice daily

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Holy basil / Ocimum tenuiflorum extract, form `10:1 whole plant`
  - Ashwagandha / Withania somnifera extract, form `Sensoril 5:1 root and leaves`
  - Cordyceps / Paecilomyces hepiali extract, form `8:1 mycelia`
  - Bacopa monnieri extract, form `BaCognize Ultra 25:1 whole herb`
- Proprietary blend hides per-component amounts; keep individual component
  amounts unknown and product-level blend amount in notes.
- Ashwagandha already has review concerns in the repo; reuse the existing card
  if form/source modeling is compatible, otherwise create a concrete Sensoril
  form.

### 11. Real Mushrooms Lion's Mane Mushroom Extract

Source:

- iHerb URL: https://www.iherb.com/pr/real-mushrooms-lion-s-mane-mushroom-extract-powder-120-capsules/112246
- Official brand page: https://realmushrooms.com/products/organic-lions-mane-extract-capsules
- Secondary source: https://www.pureformulas.com/product/lions-mane-mushroom-extract-by-real-mushrooms/1000062325

Extraction status: official Real Mushrooms page confirms product identity and
fruiting-body / beta-glucan positioning. Secondary source provides concrete
Supplement Facts.

Label facts:

- Brand: Real Mushrooms
- Product name: Lion's Mane Mushroom Extract
- Package: 120 capsules
- Serving size from secondary source: 2 capsules
- Organic Lion's Mane mushroom extract: 1,000 mg per 2 capsules
- Botanical: Hericium erinaceus
- Beta-(1,3)(1,6)-glucans: 300 mg per 2 capsules
- Product positioning: 100% fruiting bodies, not mycelium grown on grain; hot
  water extracted; more than / guaranteed 30% beta-glucans
- Other ingredients from secondary source: hypromellose vegetable capsule,
  silicon dioxide, microcrystalline cellulose; may contain stearic acid

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Lion's Mane / Hericium erinaceus extract, form `fruiting body hot water extract`
  - Beta-glucans, form `beta-(1,3)(1,6)-glucans`, possibly product component note
    rather than a standalone substance
- This tests whether marker compounds such as beta-glucans should be separate
  substances or component notes for a mushroom extract.

### 12. The Genius Brand Genius Pre

Source:

- iHerb URL: https://www.iherb.com/pr/the-genius-brand-pre-caffeine-free-blue-raspberry-10-5-oz-298-g/115936
- User-provided Supplement Facts text in chat, 2026-05-08
- Official brand page: https://thegeniusbrand.com/products/genius-pre
- Secondary source: https://www.hewyn.com/en-sa/products/caffeine-free-pre-workout-blue-raspberry

Extraction status: official brand page confirms formula components and use.
User-provided Supplement Facts text supplies serving size, servings per
container, and component amounts.

Label facts:

- Brand: The Genius Brand
- Product name: Genius Pre
- Flavor/package: Blue Raspberry, 10.5 oz / 298 g
- User hint: `pre_workout`
- Serving size: 1 scoop / 14.9 g
- Servings per container: 20
- L-Citrulline Malate 2:1: 6 g
- Beta-alanine: 2 g
- Betaine nitrate as NO3-T: 2 g
- L-Tyrosine: 1 g
- Taurine: 1 g
- HICA / alpha-hydroxyisocaproic acid: 500 mg
- Alpha-GPC 50%: 300 mg
- L-Theanine: 200 mg
- Rhodiola rosea root extract standardized to 3% salidrosides: 100 mg
- Theobromine: 30 mg
- AstraGin, Panax notoginseng root extract plus Astragalus membranaceus root
  extract: 25 mg
- Huperzia serrata whole plant extract standardized to 1% huperzine A: 10 mg
- Other ingredients from secondary source: silica, natural flavors, stevia leaf
  extract, tartaric acid, sodium chloride, spirulina extract
- Suggested use: mix 1 scoop with 8-10 oz water 20-30 minutes before exercise

Modeling notes:

- Product should become `inactive`, but keep the `pre_workout` context from the
  user hint.
- Likely substance cards to review/create:
  - L-Citrulline, form `malate`
  - Beta-alanine
  - Betaine, form `nitrate / NO3T`
  - L-Tyrosine
  - Taurine
  - HICA / alpha-hydroxyisocaproic acid
  - Alpha-GPC
  - L-Theanine
  - Rhodiola rosea extract, form `root standardized to 3% salidrosides`
  - Theobromine
  - AstraGin blend, likely product-level absorption blend unless the model needs
    Panax notoginseng / Astragalus components separately
  - Huperzine A / Huperzia serrata extract, form `1% huperzine A`
- This is a strong ontology test for pre-workout blends and whether branded
  absorption blends are substances or product notes.

### 13. NOW Foods L-OptiZinc

Source:

- iHerb URL: https://www.iherb.com/pr/now-foods-l-optizinc-100-veg-capsules/738
- Official brand page: https://www.nowfoods.com/products/supplements/l-optizinc-30-mg-veg-capsules

Extraction status: official NOW Foods page found via Exa.

Label facts:

- Brand: NOW Foods
- Product name: L-OptiZinc 30 mg
- Package: 100 veg capsules
- Serving size: 1 veg capsule
- Zinc elemental from 167 mg L-OptiZinc monomethionine: 30 mg
- Copper elemental from 3 mg copper bisglycinate: 0.3 mg
- Other ingredients: rice flour, hypromellose cellulose capsule, stearic acid,
  maltodextrin, citric acid, silicon dioxide

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Zinc, form `monomethionine / L-OptiZinc`
  - Copper, form `bisglycinate`
- This should reuse existing zinc/copper balance and competition relations if
  the concrete forms map cleanly to existing substance cards.

### 14. Solaray Zinc Copper with Kelp & Pumpkin Seed

Source:

- iHerb URL: https://www.iherb.com/pr/solaray-zinc-copper-with-kelp-pumpkin-seed-100-vegcaps/19000
- Official brand page: https://solaray.com/products/zinc-copper
- Secondary source with full Supplement Facts: https://www.pureformulas.com/product/zinc-copper-amino-acid-chelate/1000049688

Extraction status: official Solaray page confirms product and ingredients.
Secondary source provides the Supplement Facts panel in a clearer form.

Label facts:

- Brand: Solaray
- Product name: Zinc Copper
- Package: 100 VegCaps
- Serving size: 1 VegCap
- Iodine from kelp: 53 mcg
- Zinc from zinc amino acid chelate complex: 50 mg
- Copper from copper amino acid chelate complex: 2 mg
- Pumpkin seed: present as nutritive support / other ingredient
- Other ingredients: whole rice concentrate, vegetable cellulose capsule, citric
  acid from non-GMO tapioca, magnesium stearate, pumpkin seed, silica
- Suggested use: 1 VegCap daily with a meal or glass of water

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Iodine, source `kelp`
  - Zinc, form `amino acid chelate complex`
  - Copper, form `amino acid chelate complex`
  - Pumpkin seed, probably product note unless it becomes a meaningful component
- This should reuse zinc/copper balance and competition relations if form cards
  map cleanly.

### 15. Doctor's Best Stabilized R-Lipoic Acid

Source:

- iHerb URL: https://www.iherb.com/pr/doctor-s-best-stabilized-r-lipoic-acid-100-mg-180-veggie-caps/23168
- Official brand page: https://www.doctorsbest.com/products/doctor-s-best-stabilized-r-lipoic-acid-100-mg-180-veggie-caps-23168

Extraction status: official Doctor's Best page found via Exa.

Label facts:

- Brand: Doctor's Best
- Product name: Stabilized R-Lipoic Acid
- Package: 180 veggie capsules
- Serving size: 1 veggie capsule
- D-Biotin: 150 mcg
- R-Lipoic Acid from Na-RALA sodium R-alpha lipoate: 100 mg
- Other ingredients: microcrystalline cellulose, hypromellose vegetarian
  capsule, silicon dioxide, magnesium stearate, rice flour
- Suggested use: 1 capsule daily, preferably on an empty stomach

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - R-Lipoic Acid, form `Na-RALA sodium R-alpha lipoate`
  - Biotin / Vitamin B7, form `D-biotin`
- This tests whether stabilized salt forms of alpha-lipoic acid should be
  concrete forms rather than aliases of generic ALA.

### 16. Natural Factors BioCoenzymated Active B Complex

Source:

- iHerb URL: https://www.iherb.com/pr/natural-factors-biocoenzymated-active-b-complex-60-vegetarian-capsules/85648
- Official brand page: https://naturalfactors.com/products/biocoenzymated-active-b-complex

Extraction status: official Natural Factors page found via Exa.

Label facts:

- Brand: Natural Factors
- Product name: BioCoenzymated Active B Complex / Active B Complex
- Package: 60 vegetarian capsules
- Serving size: 1 vegetarian capsule
- Thiamin as hydrochloride and benfotiamine: 30 mg
- Riboflavin as riboflavin 5'-phosphate: 10 mg
- Niacin as inositol hexaniacinate: 100 mg
- Vitamin B6 as pyridoxal 5'-phosphate: 25 mg
- Folate from (6S)-5-methyltetrahydrofolic acid (MTHF), glucosamine salt,
  Quatrefolic: 680 mcg DFE / 400 mcg (6S)-5-MTHF
- Vitamin B12 as methylcobalamin: 500 mcg
- Biotin: 250 mcg
- Pantothenic acid as calcium D-pantothenate: 100 mg
- Choline as dihydrogen citrate: 50 mg
- Inositol: 25 mg
- Other ingredients: microcrystalline cellulose, vegetarian capsule with
  hypromellose and purified water, silica, magnesium stearate
- Suggested use: 1 capsule per day

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin B1, form `thiamine hydrochloride`
  - Vitamin B1, form `benfotiamine`
  - Vitamin B2, form `riboflavin 5'-phosphate`
  - Vitamin B3, form `inositol hexaniacinate`
  - Vitamin B6, form `pyridoxal 5'-phosphate`
  - Vitamin B9, form `(6S)-5-MTHF glucosamine salt / Quatrefolic`
  - Vitamin B12, form `methylcobalamin`
  - Biotin / Vitamin B7
  - Vitamin B5, form `calcium D-pantothenate`
  - Choline, form `dihydrogen citrate`
  - Inositol
- This product is a strong test for active-form B-vitamin splitting and should
  not collapse into generic B-vitamin cards.

### 17. Doctor's Best NAC Detox Regulators

Source:

- iHerb URL: https://www.iherb.com/pr/doctor-s-best-nac-detox-regulators-180-veggie-caps/95570
- Official brand page: https://www.doctorsbest.com/products/doctor-s-best-nac-detox-regulators-180-veggie-caps-95570

Extraction status: official Doctor's Best page found via Exa.

Label facts:

- Brand: Doctor's Best
- Product name: NAC Detox Regulators
- Package: 180 veggie capsules
- Serving size: 1 veggie capsule
- Selenium from SelenoExcell high selenium yeast / Saccharomyces cerevisiae:
  50 mcg
- Molybdenum from molybdenum glycinate chelate: 50 mcg
- N-Acetylcysteine / NAC: 600 mg
- Other ingredients: hypromellose vegetarian capsule, citric acid, natural
  vanilla flavor
- Suggested use: 1 capsule twice daily with food

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - N-Acetylcysteine / NAC
  - Selenium, form `SelenoExcell high selenium yeast`
  - Molybdenum, form `glycinate chelate`
- This should align with the existing NAC `supported_by` selenium/molybdenum
  model if the forms map cleanly.

### 18. NOW Foods Potassium Citrate

Source:

- iHerb URL: https://www.iherb.com/pr/now-foods-potassium-citrate-99-mg-180-veg-capsules/13061
- Official brand page: https://www.nowfoods.com/products/supplements/potassium-citrate-99-mg-veg-capsules

Extraction status: official NOW Foods page found via Exa.

Label facts:

- Brand: NOW Foods
- Product name: Potassium Citrate 99 mg
- Package: 180 veg capsules
- Serving size: 1 veg capsule
- Potassium from 310 mg potassium citrate: 99 mg
- Other ingredients: microcrystalline cellulose, hypromellose cellulose capsule,
  stearic acid, silicon dioxide
- Suggested use: 1 capsule 1-5 times daily, preferably with food

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Potassium, form `citrate`
- Existing potassium citrate substance/product cards may already cover this; use
  this intake row to enrich or add URL/source facts rather than duplicating.

### 19. Life Extension Mega Benfotiamine

Source:

- iHerb URL: https://www.iherb.com/pr/life-extension-mega-benfotiamine-250-mg-120-vegetarian-capsules/13192
- Official brand page: https://www.lifeextension.com/vitamins-supplements/item00925/mega-benfotiamine

Extraction status: official Life Extension page found via Exa.

Label facts:

- Brand: Life Extension
- Product name: Mega Benfotiamine
- Package: 120 vegetarian capsules
- Serving size: 1 vegetarian capsule
- Thiamine / Vitamin B1 as thiamine HCl: 10 mg
- Benfotiamine: 250 mg
- Other ingredients: microcrystalline cellulose, vegetable cellulose capsule,
  stearic acid, silica, vegetable stearate
- Suggested use: 1 capsule 1-4 times daily

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin B1, form `thiamine HCl`
  - Vitamin B1, form `benfotiamine`
- This overlaps with Natural Factors Benfotiamine and Active B Complex; reuse
  concrete B1 form cards where possible.

### 20. NOW Foods Magnesium Glycinate

Source:

- iHerb URL: https://www.iherb.com/pr/now-foods-magnesium-glycinate-180-tablets-100-mg-per-tablet/88819
- Official brand page: https://www.nowfoods.com/products/supplements/magnesium-glycinate-tablets

Extraction status: official NOW Foods page found via Exa.

Label facts:

- Brand: NOW Foods
- Product name: Magnesium Glycinate
- Package: 180 tablets
- Serving size: 2 tablets
- Servings per container: 90 for 180 tablets
- Magnesium elemental from magnesium bisglycinate / Albion: 200 mg per 2 tablets
- Implied amount: 100 mg elemental magnesium per tablet
- Other ingredients from secondary retailer: citric acid, hydroxypropyl
  cellulose, stearic acid, silicon dioxide, vegetarian coating
- Suggested use from secondary retailer: 2 tablets 1-2 times daily with food

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Magnesium, form `bisglycinate / Albion`
- Existing magnesium glycinate card may already cover this; enrich rather than
  duplicate if form matches.

### 21. Garden of Life Super Seed Beyond Fiber

Source:

- iHerb URL: https://www.iherb.com/pr/garden-of-life-super-seed-beyond-fiber-21-oz-600-g/3163
- Official brand page: https://www.gardenoflife.com/super-seedr-beyond-fiber-unflavored-1-lb-5-oz-600g
- Secondary source with detailed Supplement Facts: https://www.professionalsupplementcenter.com/products/super-seed-beyond-fiber-by-garden-of-life

Extraction status: official Garden of Life page confirms product identity and
core claims. Secondary source provides detailed nutrition facts and blend
components.

Label facts:

- Brand: Garden of Life
- Product name: Super Seed Beyond Fiber
- Package: 21 oz / 600 g powder
- Servings per container: 30
- Serving size: 1 scoop / about 20 g
- Calories: 70
- Total fat: 2.5 g
- Total carbohydrate: 9 g
- Dietary fiber: 6 g
- Soluble fiber: 1 g
- Insoluble fiber: 4 g
- Sugars: 0 g
- Protein: 6 g
- Calcium naturally occurring: 66 mg
- Iron naturally occurring: 2 mg
- Perfect Fiber Blend: 18 g, including organic flax seed meal and whole chia seed
- Poten-Zyme Whole Food Fiber Blend: 1.5 g, including sprouted grains, seeds,
  and legumes such as amaranth, quinoa, millet, buckwheat, garbanzo bean,
  lentil, adzuki bean, flax, sunflower seed, pumpkin seed, chia, and sesame
- Omega-3 fatty acids / alpha-linolenic acid: about 1.1 g
- Organic cinnamon: 127 mg
- Stevia: 20 mg
- Proprietary probiotic blend: 2 mg, including Lactobacillus plantarum,
  Bifidobacterium lactis, Bifidobacterium bifidum, Lactobacillus rhamnosus,
  Bifidobacterium breve, Lactobacillus casei, Lactobacillus salivarius,
  Lactobacillus acidophilus
- Suggested use: mix 1 scoop with food or beverage and consume promptly

Modeling notes:

- Product should become `inactive`.
- Likely product-level components/notes:
  - Fiber blend / seed blend
  - Alpha-linolenic acid / ALA omega-3 as product nutrition note
  - Probiotic blend as product note unless the model later needs probiotic strain
    cards
- Do not explode every grain, seed, legume, and probiotic strain into separate
  substance cards unless a concrete planner/review behavior needs it.

### 22. Paradise Herbs African Mango Extract

Source:

- iHerb URL: https://www.iherb.com/pr/paradise-herbs-african-mango-extract-150-mg-60-vegetarian-capsules/51625
- Official brand page: https://paradiseherbs.com/products/african-mango/
- Secondary source with Supplement Facts: https://www.allstarhealth.com/f/paradise_herbs-african_mango_(150mg).htm

Extraction status: official Paradise Herbs page confirms product and suggested
use. Secondary source provides clear Supplement Facts.

Label facts:

- Brand: Paradise Herbs
- Product name: African Mango
- Package: 60 vegetarian capsules
- Serving size: 1 vegetarian capsule
- African Mango seed extract 10:1 / Irvingia gabonensis: 150 mg
- Other ingredients: vegetarian capsule / plant cellulose
- Suggested use: 1 capsule 1-2 times daily 30 minutes before meals

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - African Mango / Irvingia gabonensis, form `seed extract 10:1`
- This differs from Swanson's whole seed powder and should probably be a
  different concrete form.

### 23. Swanson Full Spectrum African Mango

Source:

- iHerb URL: https://www.iherb.com/pr/swanson-full-spectrum-african-mango-400-mg-60-capsules/117790
- Official brand page: https://www.swansonvitamins.com/p/swanson-premium-full-spectrum-african-mango-400-mg-60-caps

Extraction status: official Swanson page found via Exa.

Label facts:

- Brand: Swanson
- Product name: Full Spectrum African Mango Irvingia Gabonensis
- Package: 60 capsules
- Serving size: 1 capsule
- African Mango / Irvingia gabonensis seed: 400 mg
- Other ingredients: gelatin, rice flour, silica, magnesium stearate
- Suggested use: 1 capsule per day with water

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - African Mango / Irvingia gabonensis, form `whole seed powder`
- This should not be merged with Paradise Herbs 10:1 extract unless the model
  intentionally ignores extract ratio/form.

### 24. Source Naturals Ultra-Mag

Source:

- iHerb URL: https://www.iherb.com/pr/source-naturals-ultra-mag-120-tablets/1415
- Official brand page: https://www.sourcenaturals.com/products/ultra-mag
- Secondary source with Supplement Facts: https://us.fullscript.com/catalog/products/ultra-mag-120tabs/U3ByZWU6OlZhcmlhbnQtNjk4MDM=

Extraction status: official Source Naturals page confirms five-source magnesium
and B6. Secondary sources provide Supplement Facts, but older/alternate listings
conflict on vitamin B6 amount.

Label facts:

- Brand: Source Naturals
- Product name: Ultra-Mag
- Package: 120 tablets
- Serving size: 2 tablets
- Magnesium from magnesium citrate, succinate, glycinate, malate, and taurinate:
  400 mg in several current sources
- Vitamin B6 as pyridoxine HCl: 30 mg in Fullscript/Emerson current listings;
  50 mg in some older/alternate secondary listings
- Sodium: 5 mg
- Other ingredients: stearic acid, acacia gum, modified cellulose gum,
  hydroxypropyl cellulose, magnesium stearate, silica
- Suggested use: 1 or 2 tablets daily with a meal

Modeling notes:

- Product should become `inactive`.
- Prefer `30 mg B6` unless a label image for the specific iHerb SKU confirms
  otherwise; keep `50 mg` as a source discrepancy.
- Likely substance cards to review/create:
  - Magnesium, form `citrate`
  - Magnesium, form `succinate`
  - Magnesium, form `glycinate`
  - Magnesium, form `malate`
  - Magnesium, form `taurinate`
  - Vitamin B6, form `pyridoxine HCl`
- This is a strong test for multi-form mineral products: one physical product
  may contain several practical magnesium forms.

### 25. Solgar Skin, Nails & Hair Advanced MSM Formula

Source:

- iHerb URL: https://www.iherb.com/pr/solgar-skin-nails-hair-advanced-msm-formula-120-tablets/22419
- Official brand page: https://www.solgar.com/products/skin-nails-hair-tablets

Extraction status: official Solgar page found via Exa.

Label facts:

- Brand: Solgar
- Product name: Skin, Nails & Hair Advanced MSM Formula
- Package: 120 tablets
- Serving size: 2 tablets
- Servings per container: 60
- Vitamin C as L-ascorbic acid: 120 mg
- Zinc as zinc citrate: 15 mg
- Copper as copper glycinate amino acid chelate: 2 mg
- MSM / methylsulfonylmethane as OptiMSM: 1,000 mg / 1 g
- Silicon as silicon dioxide and Lithothamnion calcareum / red algae powder:
  50 mg
- L-Proline: 50 mg
- L-Lysine as L-lysine HCl: 50 mg
- Other ingredients: microcrystalline cellulose, vegetable stearic acid,
  vegetable cellulose, vegetable magnesium stearate, vegetable glycerin
- Suggested use: 2 tablets daily, preferably with a meal

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin C, form `L-ascorbic acid`
  - Zinc, form `citrate`
  - Copper, form `glycinate amino acid chelate`
  - MSM / methylsulfonylmethane
  - Silicon, form `silicon dioxide / red algae powder`
  - L-Proline
  - L-Lysine, form `HCl`
- This overlaps with collagen/skin-barrier ontology facts and the zinc/copper
  balance model.

### 26. Source Naturals Calcium Hydroxyapatite

Source:

- iHerb URL: https://www.iherb.com/pr/source-naturals-calcium-hydroxyapatite-120-capsules/55874
- Official brand page: https://www.sourcenaturals.com/products/calcium-hydroxyapatite
- Secondary source with Supplement Facts: https://vitanetonline.com/description/SN2521/vitamins/Calcium-Hydroxyapatite/

Extraction status: official Source Naturals page confirms the product and use
directions. Secondary sources provide Supplement Facts; some listings differ
slightly on calcium and vitamin D amounts.

Label facts:

- Brand: Source Naturals
- Product name: Calcium Hydroxyapatite
- Package: 120 capsules
- Serving size: 3 capsules
- Protein: 1 g
- Vitamin D3 as cholecalciferol: 12 mcg / 480 IU in current secondary listing
- Calcium as microcrystalline calcium hydroxyapatite and dibasic calcium
  phosphate: 636 mg in current secondary listing
- Phosphorus from microcrystalline calcium hydroxyapatite: 245 mg
- Microcrystalline calcium hydroxyapatite: 2.7 g
- Other ingredients: gelatin capsule, dibasic calcium phosphate, magnesium
  stearate, silica
- Suggested use: 3 capsules twice daily

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Calcium, form `microcrystalline hydroxyapatite`
  - Calcium, form `dibasic calcium phosphate`
  - Phosphorus
  - Vitamin D3, form `cholecalciferol`
- This tests calcium forms and the calcium/phosphorus/vitamin D cluster.

### 27. Universal U Daily Formula The Everyday Multi-Vitamin

Source:

- iHerb URL: https://www.iherb.com/pr/universal-u-daily-formula-the-everyday-multi-vitamin-100-tablets-discontinued-item/41356
- Official brand page: https://www.universalusa.com/product/daily-formula/
- Secondary source with Supplement Facts: https://www.hpnutrition.ie/products/universal-nutrition-daily-formula
- Secondary source with alternate Supplement Facts:
  https://www.globevitamin.com/products/daily-formula-100-tablets-universal

Extraction status: official Universal page confirms the current product shape
and use directions, but full label facts came from secondary sources. Secondary
sources disagree on several amounts, so this needs label-image verification
before YAML encoding.

Label facts:

- Brand: Universal / Universal Nutrition
- Product name: Daily Formula / The Everyday Multi-Vitamin
- Package: 100 tablets on the iHerb discontinued listing
- Serving size: 1 tablet
- Current official page describes 23 required nutrients plus a digestive enzyme
  complex
- Commonly reported components include vitamins A, C, D, E, K, B1, B2, B3, B5,
  B6, B12, folate, biotin, calcium, phosphorus, iodine, magnesium, zinc,
  selenium, copper, manganese, chromium, molybdenum, and digestive enzymes
- Reported B6 form: pyridoxine HCl in one secondary source
- Reported B12 forms conflict: cyanocobalamin in one source; another source
  lists B12 without a form
- Reported enzyme complex includes papain, diastase malt, and lipase in one
  source
- Suggested use: 1 tablet daily

Modeling notes:

- Product should become `inactive`.
- Do not encode exact doses from this pass without a more reliable label image.
- Likely substance cards to review/create are the common multivitamin
  vitamins/minerals plus digestive enzymes.
- This is a good test case for formula drift and discontinued iHerb listings.

### 28. ALLMAX Essentials Caffeine

Source:

- iHerb URL: https://www.iherb.com/pr/allmax-essentials-caffeine-200-mg-100-tablets/67652
- Official brand page: https://www.allmaxnutrition.com/products/allmax-caffeine-100-tabs
- Secondary source with Supplement Facts: https://www.fitshop.ca/Allmax-Nutrition-Caffeine-200-mg-ALLMAX-CAFFEINE

Extraction status: official ALLMAX page confirms 200 mg caffeine tablets.
Secondary source provides the inactive ingredient list.

Label facts:

- Brand: ALLMAX Essentials / ALLMAX Nutrition
- Product name: Caffeine
- Package: 100 tablets
- Serving size: 1 tablet
- Caffeine anhydrous: 200 mg
- Other ingredients reported: calcium sulfate dihydrate, dicalcium phosphate,
  compressible sugar, pregelatinized starch, microcrystalline cellulose,
  magnesium stearate, silicon dioxide, stearic acid
- Suggested use: 1 tablet; secondary source says not more often than every 3-4
  hours and not more than 1,000 mg per 24 hours

Modeling notes:

- Product should become `inactive`.
- Likely substance card to review/create:
  - Caffeine, form `anhydrous`
- This is an ingestible drug-like/stimulant product and is still in scope.

### 29. Ready In Case Aspirin

Source:

- iHerb URL: https://www.iherb.com/pr/ready-in-case-aspirin-81-mg-300-enteric-coated-tablets/38964
- Indexed iHerb page found via Exa
- Regulatory cross-check: https://dailymed.nlm.nih.gov/

Extraction status: indexed iHerb drug-facts content found via search. DailyMed
has matching low-dose aspirin drug-facts patterns, but the exact Ready In Case
label should still be treated as source-specific.

Label facts:

- Brand: Ready In Case
- Product name: Aspirin
- Package: 300 enteric-coated tablets
- Serving/unit: 1 tablet
- Active ingredient: Aspirin / acetylsalicylic acid 81 mg
- Purpose on label: NSAID pain reliever
- Inactive ingredients reported: D&C yellow #10, FD&C yellow #6, methacrylic
  acid copolymer, microcrystalline cellulose, pregelatinized corn starch,
  silicon dioxide, sodium bicarbonate, sodium lauryl sulfate, stearic acid,
  talc, titanium dioxide, triethyl citrate
- Label notes that enteric coating delays action and is not for fast headache
  relief

Modeling notes:

- Product should become `inactive`.
- Likely substance card to review/create:
  - Aspirin / acetylsalicylic acid, form `enteric-coated low-dose tablet`
- OTC/drug-like products remain in scope because the project tracks ingested
  products, not only supplements.
- Later ontology review should consider antiplatelet/bleeding-risk stacking
  with omega-3, nattokinase, and similar substances.

### 30. Controlled Labs Orange Triad

Source:

- iHerb URL: https://www.iherb.com/pr/controlled-labs-orange-triad-multi-vitamin-joint-digestion-immune-formula-270-tablets/24674
- Official brand page: https://www.controlledlabs.com/products/orange-triad
- Secondary source with Supplement Facts: https://www.dpsnutrition.net/i/11637/controlled-labs-orange-triad-270-tablets.htm

Extraction status: official Controlled Labs page confirms product positioning,
package size, and use directions. Full Supplement Facts came from a secondary
retailer; complex-blend details should be verified from a label image before
YAML encoding.

Label facts:

- Brand: Controlled Labs
- Product name: Orange Triad
- Package: 270 tablets / 45 servings
- Serving size: 6 tablets
- Suggested use: 3 tablets twice per day with meals
- Core vitamins/minerals reported: vitamins A, C, D, E, K, B1, B2, B3, B5, B6,
  B12, folic acid, biotin, calcium, phosphorus, iodine, magnesium, zinc,
  selenium, copper, manganese, chromium, molybdenum, and potassium
- Reported forms include vitamin D as cholecalciferol, vitamin K as
  phytonadione, thiamine HCl, niacin as inositol hexanicotinate, B12 as
  methylcobalamin, calcium citrate/calcium D-glucarate/dicalcium phosphate,
  zinc citrate, and potassium chloride
- Joint Complex: glucosamine sulfate and chondroitin sulfate
- Flex Complex: MSM, bromelain, and hyaluronic acid
- Digestion and immune blend reported by secondary sources includes multiple
  botanicals/polyphenols such as ginger, quercetin, R-alpha-lipoic acid,
  bilberry, blueberry, pomegranate, grape seed, lycopene, and lutein
- Allergens reported: fish, shellfish, and soy

Modeling notes:

- Product should become `inactive`.
- Do not explode every low-confidence blend constituent into YAML until the
  exact label is verified.
- Likely substance cards to review/create include multivitamin/mineral
  components, glucosamine sulfate, chondroitin sulfate, MSM, bromelain,
  hyaluronic acid, and verified blend constituents.
- This is a high-value ontology stress test for multivitamin plus joint plus
  digestion/immune blends.

### 31. Source Naturals Advanced Ferrochel

Source:

- iHerb URL: https://www.iherb.com/pr/source-naturals-advanced-ferrochel-180-tablets/1021
- Secondary source with Supplement Facts: https://www.vitacost.com/source-naturals-advanced-ferrochel-iron
- Secondary source with Supplement Facts:
  https://supplements.market/product/source-naturals-advanced-ferrochel-180-tablets/

Extraction status: secondary sources agree on the main iron dose and form.
Several sources differ on B12 form/amount and whether calcium is listed, so the
specific iHerb label should be verified before YAML encoding.

Label facts:

- Brand: Source Naturals
- Product name: Advanced Ferrochel
- Package: 180 tablets
- Serving size: 1 tablet
- Vitamin C as ascorbic acid: 60 mg
- Folate as folic acid: 340 mcg DFE / 200 mcg folic acid in current-format
  sources
- Vitamin B12: 25 mcg in current-format sources; one older source reports
  methylcobalamin 60 mcg
- Iron as Ferrochel ferrous bisglycinate chelate: 27 mg
- Other ingredients reported: dibasic calcium phosphate, microcrystalline
  cellulose, stearic acid, hydroxypropyl cellulose / modified cellulose gum,
  silica, magnesium stearate
- Suggested use: 1 tablet daily
- Warning: iron-containing products can be dangerous in accidental overdose,
  especially for children

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Iron, form `ferrous bisglycinate chelate / Ferrochel`
  - Vitamin C, form `ascorbic acid`
  - Folate, form `folic acid`
  - Vitamin B12, form unknown until label verification
- Later relation review should consider calcium/iron spacing and iron
  absorption support by vitamin C.

### 32. Source Naturals Male Response

Source:

- iHerb URL: https://www.iherb.com/pr/source-naturals-male-response-90-tablets/1272
- Secondary source with Supplement Facts:
  https://www.nutrivera.com/mens-health/source-naturals-male-response-90-tablets/

Extraction status: iHerb page confirms the product, suggested use, and warning
language. Full Supplement Facts came from a secondary retailer and should be
verified against a label image before YAML encoding.

Label facts:

- Brand: Source Naturals
- Product name: Male Response
- Package: 90 tablets
- Serving size: 3 tablets
- Servings per container: 30
- Vitamin E as vitamin E succinate: 100 IU
- Vitamin B6 as pyridoxine HCl: 25 mg
- Pantothenic acid as calcium D-pantothenate: 50 mg
- Zinc as OptiZinc monomethionine: 15 mg
- Selenium as L-selenomethionine and sodium selenite: 150 mcg
- Copper as copper sebacate: 1 mg
- Tribulus fruit extract: 500 mg, yielding 240 mg saponins
- Maca root: 300 mg
- Epimedium aerial parts extract: 300 mg, 10% flavonoids as icariin
- Yohimbe bark extract: 225 mg, yielding 9 mg yohimbines
- Asian ginseng root extract: 210 mg
- Damiana leaf: 200 mg
- Saw palmetto root/root extract: 200 mg
- Sarsaparilla root: 200 mg
- Eleuthero root extract 5:1: 200 mg
- L-Arginine as L-arginine pyroglutamate: 300 mg
- Ashwagandha root extract 5:1: 250 mg
- Ginkgo leaf extract: 60 mg
- Ginger root: 60 mg
- Stinging nettle root extract 10:1: 60 mg
- Suggested use on iHerb: 3 tablets per day
- Warning: contains yohimbine; avoid with high blood pressure, heart/prostate
  conditions, kidney disease, antidepressants, and prescription drugs unless
  cleared by a clinician

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create include yohimbe/yohimbine, tribulus,
  maca, epimedium/icariin, ginseng, damiana, saw palmetto, sarsaparilla,
  eleuthero, L-arginine pyroglutamate, ashwagandha, ginkgo, ginger, nettle,
  OptiZinc, selenium forms, and copper sebacate.
- This product is a strong safety/relation test because yohimbine changes the
  practical risk profile more than ordinary supplement blends.

### 33. Optimum Nutrition Opti-Men

Source:

- iHerb URL: https://www.iherb.com/pr/optimum-nutrition-opti-men-multivitamin-for-active-men-150-tablets/57069
- Official brand page: https://www.optimumnutrition.com/

Extraction status: iHerb page exposes full Supplement Facts and product
directions.

Label facts:

- Brand: Optimum Nutrition
- Product name: Opti-Men / Multivitamin for Active Men
- Package: 150 tablets
- Serving size: 3 tablets
- Servings per container: 50
- Suggested use: consume 3 tablets with food; limit 1 serving per day
- Vitamins/minerals reported: vitamins A, C, D, E, K, B1, B2, B3, B5, B6, B12,
  folate, biotin, choline, calcium, iodine, magnesium, zinc, selenium, copper,
  manganese, chromium, molybdenum, and sodium
- Reported forms include vitamin A as beta carotene/mixed carotenoids, vitamin C
  as ascorbic acid, vitamin D as cholecalciferol, vitamin E as d-alpha
  tocopheryl succinate, vitamin K as phytonadione, thiamin HCl, niacinamide,
  pyridoxine HCl, folic acid, cyanocobalamin, calcium D-pantothenate,
  dicalcium phosphate, potassium iodide, magnesium oxide/aspartate, zinc oxide,
  L-selenomethionine, copper sulfate, manganese sulfate, chromium nicotinate
  glycinate chelate, molybdenum amino acid chelate, boron citrate, and vanadium
  citrate
- Amino Men Blend: L-arginine, L-glutamine, L-lysine, L-cystine, L-isoleucine,
  L-leucine, L-valine, L-threonine: 1 g total
- Phyto Men Blend: green tea extract, hesperidin, garlic powder, grape extract,
  fruit/vegetable powders, bilberry, black currant, blueberry, cranberry,
  elderberry, kiwi, papaya, and related botanicals: 100 mg total
- Viri Men Blend: Panax ginseng, nettle, gum arabic, ginkgo, saw palmetto,
  oyster extract, pumpkin seed: 50 mg total
- Enzyme Blend: papain, bromelain, alpha amylase, lipase: 50 mg total
- Alpha lipoic acid: 25 mg
- Inositol: 10 mg
- Lycopene: 501 mcg
- Lutein: 501 mcg
- Zeaxanthin: 28 mcg
- Other ingredients: microcrystalline cellulose, stearic acid, HPMC,
  croscarmellose sodium, magnesium stearate, silica, glycerine, sunflower oil,
  carnauba wax

Modeling notes:

- Product should become `inactive`.
- This is a high-complexity multivitamin. Prefer exact top-level vitamin/mineral
  components first; blend constituents can be added after deciding how much
  low-dose proprietary blends should be exploded into substance cards.
- This overlaps with many existing substances and is useful for formula-drift
  and blend-model stress testing.

### 34. Natrol Melatonin Calm Sleep Fast Dissolve

Source:

- iHerb URL: https://www.iherb.com/pr/natrol-melatonin-calm-sleep-fast-dissolve-strawberry-60-tablets-discontinued-item/36898
- Secondary source with Supplement Facts:
  https://melatonin.asia/pages/natrol-calm-sleep-supplement-fact
- Secondary retail/review page:
  https://www.iherb.com/r/Natrol-Melatonin-Calm-Sleep-Fast-Dissolve-Strawberry-60-Tablets/36898

Extraction status: discontinued iHerb product. Secondary source provides the
clearest Supplement Facts for the Calm Sleep formula; verify before YAML
encoding.

Label facts:

- Brand: Natrol
- Product name: Melatonin Calm Sleep Fast Dissolve
- Flavor/package: strawberry, 60 tablets
- Serving size: 1 tablet
- L-Theanine: 25 mg
- Melatonin: 6 mg
- Other ingredients reported: xylitol, cellulose gum, soy polysaccharides,
  maltodextrin, dextrose, crospovidone, modified food starch, malic acid,
  silicon dioxide, natural flavor system, stearic acid, beet root extract,
  hydroxypropyl cellulose, magnesium stearate, citric acid
- Contains: wheat and soy in the secondary label source

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Melatonin
  - L-Theanine
- This overlaps with sleep-slot logic and is a good test for fast-dissolve /
  bedtime-only products.

### 35. Country Life Core Daily-1 Multivitamin for Women

Source:

- iHerb URL: https://www.iherb.com/pr/country-life-core-daily-1-multivitamin-for-women-60-tablets/34145
- Official brand page:
  https://countrylifevitamins.com/products/core-daily-1-for-women

Extraction status: official Country Life page provides full Supplement Facts.

Label facts:

- Brand: Country Life
- Product name: Core Daily-1 for Women
- Package: 60 tablets
- Serving size: 1 tablet
- Suggested use: adult females take 1 tablet daily with food
- Vitamins/minerals reported: vitamins A, C, D3, E, K1, B1, B2, B3, B5, B6,
  B12, folate, biotin, calcium, iron, phosphorus, magnesium, zinc, selenium,
  copper, manganese, chromium, molybdenum, potassium, and choline
- Reported forms include beta carotene, calcium ascorbate/amla/acerola,
  cholecalciferol, d-alpha tocopheryl acid succinate, phytonadione K1, thiamine
  HCl/thiamine cocarboxylase chloride, riboflavin/riboflavin-5-phosphate,
  inositol hexanicotinate, pyridoxine HCl/P5P, methylfolate-glucosamine salt,
  cyanocobalamin/methylcobalamin, calcium hydroxyapatite/fructoborate,
  ferrous gluconate, magnesium oxide/citrate, zinc monomethionine, sodium
  selenate, copper amino acid chelate, chromium picolinate, and potassium
  citrate
- Women's Health Blend: cranberry, grape seed, pomegranate, quercetin,
  blueberry, resveratrol, tart cherry, strawberry, raspberry seed, bilberry,
  prune, calcium fructoborate, and ginger extract: 207.5 mg total

Modeling notes:

- Product should become `inactive`.
- This is another multivitamin stress test, but official facts are stronger than
  many discontinued-product sources.
- Likely new/review substances include iron as ferrous gluconate, vitamin K1,
  thiamine cocarboxylase chloride, riboflavin-5-phosphate, calcium
  fructoborate, chromium picolinate, and blend botanicals if we decide they are
  worth modeling.

### 36. Nature's Way Alive Calcium Max Absorption

Source:

- iHerb URL: https://www.iherb.com/pr/nature-s-way-alive-calcium-max-absorption-120-tablets/43056
- Secondary source with Supplement Facts:
  https://www.vitacost.com/natures-way-alive-calcium-max-absorption
- NIH DSLD PDF found via search:
  https://api.ods.od.nih.gov/dsld/s3/pdf/273360.pdf

Extraction status: secondary sources provide full Supplement Facts and agree on
the key calcium/D3/K2/magnesium structure.

Label facts:

- Brand: Nature's Way
- Product name: Alive Calcium Max Absorption
- Package: 120 tablets
- Serving size: 4 tablets
- Servings per container: 30
- Vitamin D3 as cholecalciferol: 100 mcg
- Calcium from Aquamin calcified mineral source red algae / Lithothamnion sp.:
  1,300 mg in current secondary listing
- Magnesium from Aquamin, magnesium citrate, and magnesium oxide: 273 mg
- Sodium: 30 mg
- Orchard Fruits & Garden Veggies blend: 100 mg
- Strontium from Aquamin: 9 mg
- Vitamin K2 as menaquinone-7 from natto / fermented soybean extract: 150 mcg
- Suggested use: adults take 4 tablets daily, preferably with food; best as 2
  tablets twice daily with food

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Calcium, form/source `Aquamin red algae`
  - Magnesium, forms `Aquamin red algae`, `citrate`, `oxide`
  - Vitamin D3, form `cholecalciferol`
  - Vitamin K2, form `menaquinone-7 / MK-7`
  - Strontium
- This tests calcium splitting, high-dose calcium spacing, and K2 MK-7 handling.

### 37. Natural Balance Happy Sleeper

Source:

- iHerb URL: https://www.iherb.com/pr/natural-balance-happy-sleeper-60-vegcaps/33841
- Official brand page:
  https://naturalbalance.com/products/happy-sleeper-the-sleep-support-blend
- Secondary source with Supplement Facts:
  https://www.vitacost.com/natural-balance-happy-sleeper

Extraction status: iHerb and secondary sources expose matching Supplement Facts.

Label facts:

- Brand: Natural Balance
- Product name: Happy Sleeper
- Package: 60 vegetarian capsules / VegCaps
- Serving size: 2 VegCaps
- Servings per container: 30
- Vitamin B6 as pyridoxine HCl: 10 mg
- 5-HTP as Griffonia simplicifolia seed extract: 50 mg
- Melatonin: 3 mg
- Happy Sleeper Blend: 550 mg total
- Blend constituents: valerian root extract supplying 0.8% valerenic acid,
  GABA, glycine, passionflower flowering tops extract, lemon balm herb, English
  lavender flower, L-theanine
- Other ingredients: vegetable cellulose capsule, cellulose, magnesium stearate,
  silica; some older/secondary sources also list maltodextrin
- Suggested use: take 2 vegetarian capsules before bedtime

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin B6, form `pyridoxine HCl`
  - 5-HTP
  - Melatonin
  - Valerian
  - GABA
  - Glycine
  - Passionflower
  - Lemon balm
  - Lavender
  - L-Theanine
- This is a sleep-stack stress test and overlaps with bedtime/sedating traits.

### 38. Source Naturals DMAE

Source:

- iHerb URL: https://www.iherb.com/pr/source-naturals-dmae-351-mg-200-tablets/1206
- Secondary source with Supplement Facts:
  https://www.vitacost.com/Source-Naturals-DMAE-351-mg-200-Tablets
- Source Naturals legacy product PDF:
  https://willner.com/desc/20679.pdf

Extraction status: secondary sources agree on the core DMAE amount and form.

Label facts:

- Brand: Source Naturals
- Product name: DMAE
- Package: 200 tablets
- Serving size: 1 tablet
- DMAE: 130 mg, from 351 mg DMAE bitartrate
- Suggested use: 1 tablet 1-2 times daily in secondary listing

Modeling notes:

- Product should become `inactive`.
- Likely substance card to review/create:
  - DMAE / dimethylaminoethanol, form `bitartrate`
- This is a simple single-substance product compared with the multivitamin and
  blend products in this batch.

### 39. Life Extension Melatonin

Source:

- iHerb URL: https://kz.iherb.com/pr/life-extension-melatonin-300-mcg-100-vegetarian-capsules/47809
- Official brand page:
  https://www.lifeextension.com/vitamins-supplements/item01668/melatonin

Extraction status: official Life Extension page provides full Supplement Facts.

Label facts:

- Brand: Life Extension
- Product name: Melatonin
- Package: 100 vegetarian capsules
- Serving size: 1 vegetarian capsule
- Melatonin: 300 mcg
- Other ingredients: microcrystalline cellulose, vegetable cellulose capsule,
  silica
- Suggested use: 1 capsule 30-60 minutes before bedtime; take at night for
  optimal results
- Caution: do not consume alcohol, drive, or operate machinery after taking

Modeling notes:

- Product should become `inactive`.
- Likely substance card to review/create:
  - Melatonin
- This is useful as the low-dose contrast to 3 mg, 6 mg, and 10 mg melatonin
  products.

### 40. Animal Flex Comprehensive Joint Care

Source:

- iHerb URL: https://kz.iherb.com/pr/animal-flex-comprehensive-joint-care-44-pill-packs/27238
- iHerb regional page with Supplement Facts:
  https://ae.iherb.com/pr/animal-flex-comprehensive-joint-care-44-pill-packs/27238

Extraction status: iHerb page exposes full Supplement Facts.

Label facts:

- Brand: Animal
- Product name: Animal Flex Comprehensive Joint Care
- Package: 44 pill packs
- Serving size: 1 pack
- Servings per container: 44
- Calories: 10
- Total fat: 1 g
- Vitamin C as ascorbic acid: 100 mg
- Vitamin E as d-alpha tocopherol succinate: 64 mg
- Zinc as zinc oxide: 15 mg
- Selenium as sodium selenite: 70 mcg
- Manganese as manganese sulfate: 1 mg
- Joint Construction Complex: 3,000 mg total; glucosamine as HCl/sulfate 2KCl,
  MSM, chondroitin sulfate A, chondroitin sulfate C
- Joint Lubrication Complex: 1,000 mg total; flaxseed oil with 50% alpha
  linolenic acid, cetyl myristoleate proprietary blend, hyaluronic acid
- Joint Support Complex: 1,000 mg total; ginger root, turmeric root, Boswellia
  serrata gum extract, quercetin dihydrate, bromelain
- Other ingredients: dicalcium phosphate, maltodextrin, bovine gelatin,
  glycerin, stearic acid, magnesium stearate, microcrystalline cellulose, carob
  extract, purified water, silicon dioxide, pharmaceutical glaze
- Contains shellfish and soy; made on equipment that processes common allergens
- Suggested use: take 1 pack with any meal during the day

Modeling notes:

- Product should become `inactive`.
- Likely substance cards to review/create:
  - Vitamin C, form `ascorbic acid`
  - Vitamin E, form `d-alpha tocopherol succinate`
  - Zinc, form `oxide`
  - Selenium, form `sodium selenite`
  - Manganese, form `sulfate`
  - Glucosamine, forms `HCl` and `sulfate 2KCl`
  - MSM
  - Chondroitin sulfate A
  - Chondroitin sulfate C
  - Flaxseed oil / alpha-linolenic acid
  - Cetyl myristoleate blend
  - Hyaluronic acid
  - Ginger
  - Turmeric / curcumin
  - Boswellia serrata
  - Quercetin dihydrate
  - Bromelain
- This is the strongest joint-support cluster in the intake batch and likely
  belongs in later skin/connective-tissue/joint goal grooming.

## Batch Notes

- Direct `curl` to iHerb currently returns a Cloudflare challenge, so extraction
  needs browser/search fallback or another reliable product-label source.
- Exa search can find official brand pages and secondary retailers for at least
  some products; prefer official brand pages when available.
- Product #12 has a user-supplied `pre_workout` hint and should become inactive
  inventory with a pre-workout product/substance context when encoded.
- Discontinued products can still be useful for the knowledge base, but their
  labels need extra source checking before YAML cards are created.

## Post-Intake Grooming Candidates

After all product facts are extracted, run a separate ontology/goal grooming
pass before creating new goals. Do not add these goals during intake extraction.

Possible clusters to review:

- digestive / gut support: fiber blends, probiotic blends, enzymes, gut-relevant
  botanicals;
- skin / hair / nails / collagen support: MSM, silicon, zinc/copper, vitamin C,
  L-proline, L-lysine, carotenoids;
- eye / macula support: lutein, zeaxanthin forms, astaxanthin;
- workout / performance: pre-workout amino acids, NO-pathway substances,
  beta-alanine, creatine-like performance compounds;
- glucose / metabolism: benfotiamine, R-lipoic acid, chromium-like or
  metabolism-focused formulas if they appear;
- stress / adaptogens: ashwagandha, bacopa, holy basil, cordyceps, rhodiola;
- sleep support: melatonin and calming formulas;
- mineral balance: magnesium, calcium, zinc, copper, potassium, iodine, iron.

Goal candidates already suggested:

- digestive support;
- skin health / skin barrier support.

The grooming pass should cluster the extracted substances/products first, then
decide which `data/goals/` files are useful. Goals are descriptive review
clusters and should not become scheduler logic.
