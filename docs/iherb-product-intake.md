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
| 1 | https://kz.iherb.com/pr/jarrow-formulas-toco-sorb-60-softgels/137 | Jarrow Formulas Toco-Sorb, 60 softgels | inactive | pending label extraction |
| 2 | https://kz.iherb.com/pr/now-foods-buffered-c-1000-complex-90-tablets/117137 | NOW Foods Buffered C-1000 Complex, 90 tablets | inactive | pending label extraction |
| 3 | https://kz.iherb.com/pr/california-gold-nutrition-nicotinamide-riboside-tartrate-nrt-complex-60-veggie-capsules/146469 | California Gold Nutrition Nicotinamide Riboside Tartrate NRT Complex, 60 veggie capsules | inactive | pending label extraction |
| 4 | https://www.iherb.com/pr/swanson-tocotrienols-100-mg-60-liquid-caps/118598 | Swanson Tocotrienols, 100 mg, 60 liquid caps | inactive | pending label extraction |
| 5 | https://www.iherb.com/pr/life-extension-vitamins-d-and-k-with-sea-iodine-60-capsules/78779 | Life Extension Vitamins D and K with Sea-Iodine, 60 capsules | inactive | pending label extraction |
| 6 | https://www.iherb.com/pr/natural-factors-astaxanthin-plus-4-mg-60-softgels/101667 | Natural Factors Astaxanthin Plus, 4 mg, 60 softgels | inactive | pending label extraction |
| 7 | https://www.iherb.com/pr/jarrow-formulas-maculapf-carotenoid-complex-60-softgels-discontinued-item/99886 | Jarrow Formulas MaculaPF Carotenoid Complex, 60 softgels, discontinued item | inactive | pending label extraction |
| 8 | https://www.iherb.com/pr/swanson-100-pure-krill-oil-60-softgels/109010 | Swanson 100% Pure Krill Oil, 60 softgels | inactive | pending label extraction |
| 9 | https://www.iherb.com/pr/natural-factors-benfotiamine-30-vegetarian-capsules-165-mg-per-capsule/85656 | Natural Factors Benfotiamine, 30 vegetarian capsules, 165 mg per capsule | inactive | pending label extraction |
| 10 | https://www.iherb.com/pr/life-extension-adrenal-energy-formula-120-vegetarian-capsules/87138 | Life Extension Adrenal Energy Formula, 120 vegetarian capsules | inactive | pending label extraction |
| 11 | https://www.iherb.com/pr/real-mushrooms-lion-s-mane-mushroom-extract-powder-120-capsules/112246 | Real Mushrooms Lion's Mane Mushroom Extract Powder, 120 capsules | inactive | pending label extraction |
| 12 | https://www.iherb.com/pr/the-genius-brand-pre-caffeine-free-blue-raspberry-10-5-oz-298-g/115936 | The Genius Brand Pre, caffeine free, blue raspberry, 10.5 oz / 298 g | inactive; pre_workout | pending label extraction |
| 13 | https://www.iherb.com/pr/now-foods-l-optizinc-100-veg-capsules/738 | NOW Foods L-OptiZinc, 100 veg capsules | inactive | pending label extraction |
| 14 | https://www.iherb.com/pr/solaray-zinc-copper-with-kelp-pumpkin-seed-100-vegcaps/19000 | Solaray Zinc Copper with Kelp & Pumpkin Seed, 100 vegcaps | inactive | pending label extraction |
| 15 | https://www.iherb.com/pr/doctor-s-best-stabilized-r-lipoic-acid-100-mg-180-veggie-caps/23168 | Doctor's Best Stabilized R-Lipoic Acid, 100 mg, 180 veggie caps | inactive | pending label extraction |
| 16 | https://www.iherb.com/pr/natural-factors-biocoenzymated-active-b-complex-60-vegetarian-capsules/85648 | Natural Factors BioCoenzymated Active B Complex, 60 vegetarian capsules | inactive | pending label extraction |
| 17 | https://www.iherb.com/pr/doctor-s-best-nac-detox-regulators-180-veggie-caps/95570 | Doctor's Best NAC Detox Regulators, 180 veggie caps | inactive | pending label extraction |
| 18 | https://www.iherb.com/pr/now-foods-potassium-citrate-99-mg-180-veg-capsules/13061 | NOW Foods Potassium Citrate, 99 mg, 180 veg capsules | inactive | pending label extraction |
| 19 | https://www.iherb.com/pr/life-extension-mega-benfotiamine-250-mg-120-vegetarian-capsules/13192 | Life Extension Mega Benfotiamine, 250 mg, 120 vegetarian capsules | inactive | pending label extraction |
| 20 | https://www.iherb.com/pr/now-foods-magnesium-glycinate-180-tablets-100-mg-per-tablet/88819 | NOW Foods Magnesium Glycinate, 180 tablets, 100 mg per tablet | inactive | pending label extraction |
| 21 | https://www.iherb.com/pr/garden-of-life-super-seed-beyond-fiber-21-oz-600-g/3163 | Garden of Life Super Seed Beyond Fiber, 21 oz / 600 g | inactive | pending label extraction |
| 22 | https://www.iherb.com/pr/paradise-herbs-african-mango-extract-150-mg-60-vegetarian-capsules/51625 | Paradise Herbs African Mango Extract, 150 mg, 60 vegetarian capsules | inactive | pending label extraction |
| 23 | https://www.iherb.com/pr/swanson-full-spectrum-african-mango-400-mg-60-capsules/117790 | Swanson Full Spectrum African Mango, 400 mg, 60 capsules | inactive | pending label extraction |
| 24 | https://www.iherb.com/pr/source-naturals-ultra-mag-120-tablets/1415 | Source Naturals Ultra-Mag, 120 tablets | inactive | pending label extraction |
| 25 | https://www.iherb.com/pr/solgar-skin-nails-hair-advanced-msm-formula-120-tablets/22419 | Solgar Skin, Nails & Hair Advanced MSM Formula, 120 tablets | inactive | pending label extraction |
| 26 | https://www.iherb.com/pr/source-naturals-calcium-hydroxyapatite-120-capsules/55874 | Source Naturals Calcium Hydroxyapatite, 120 capsules | inactive | pending label extraction |
| 27 | https://www.iherb.com/pr/universal-u-daily-formula-the-everyday-multi-vitamin-100-tablets-discontinued-item/41356 | Universal U Daily Formula The Everyday Multi-Vitamin, 100 tablets, discontinued item | inactive | pending label extraction |
| 28 | https://www.iherb.com/pr/allmax-essentials-caffeine-200-mg-100-tablets/67652 | ALLMAX Essentials Caffeine, 200 mg, 100 tablets | inactive | pending label extraction |
| 29 | https://www.iherb.com/pr/ready-in-case-aspirin-81-mg-300-enteric-coated-tablets/38964 | Ready In Case Aspirin, 81 mg, 300 enteric coated tablets | inactive | pending label extraction |
| 30 | https://www.iherb.com/pr/controlled-labs-orange-triad-multi-vitamin-joint-digestion-immune-formula-270-tablets/24674 | Controlled Labs Orange Triad Multi-Vitamin Joint Digestion Immune Formula, 270 tablets | inactive | pending label extraction |
| 31 | https://www.iherb.com/pr/source-naturals-advanced-ferrochel-180-tablets/1021 | Source Naturals Advanced Ferrochel, 180 tablets | inactive | pending label extraction |
| 32 | https://www.iherb.com/pr/source-naturals-male-response-90-tablets/1272 | Source Naturals Male Response, 90 tablets | inactive | pending label extraction |
| 33 | https://www.iherb.com/pr/optimum-nutrition-opti-men-multivitamin-for-active-men-150-tablets/57069 | Optimum Nutrition Opti-Men Multivitamin for Active Men, 150 tablets | inactive | pending label extraction |
| 34 | https://www.iherb.com/pr/natrol-melatonin-calm-sleep-fast-dissolve-strawberry-60-tablets-discontinued-item/36898 | Natrol Melatonin Calm Sleep Fast Dissolve, strawberry, 60 tablets, discontinued item | inactive | pending label extraction |
| 35 | https://www.iherb.com/pr/country-life-core-daily-1-multivitamin-for-women-60-tablets/34145 | Country Life Core Daily-1 Multivitamin for Women, 60 tablets | inactive | pending label extraction |
| 36 | https://www.iherb.com/pr/nature-s-way-alive-calcium-max-absorption-120-tablets/43056 | Nature's Way Alive Calcium Max Absorption, 120 tablets | inactive | pending label extraction |
| 37 | https://www.iherb.com/pr/natural-balance-happy-sleeper-60-vegcaps/33841 | Natural Balance Happy Sleeper, 60 vegcaps | inactive | pending label extraction |
| 38 | https://www.iherb.com/pr/source-naturals-dmae-351-mg-200-tablets/1206 | Source Naturals DMAE, 351 mg, 200 tablets | inactive | pending label extraction |
| 39 | https://kz.iherb.com/pr/life-extension-melatonin-300-mcg-100-vegetarian-capsules/47809 | Life Extension Melatonin, 300 mcg, 100 vegetarian capsules | inactive | pending label extraction |
| 40 | https://kz.iherb.com/pr/animal-flex-comprehensive-joint-care-44-pill-packs/27238 | Animal Flex Comprehensive Joint Care, 44 pill packs | inactive | pending label extraction |

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
- Official brand page: https://thegeniusbrand.com/products/genius-pre
- Secondary source: https://www.hewyn.com/en-sa/products/caffeine-free-pre-workout-blue-raspberry

Extraction status: official brand page confirms formula components and use.
Secondary source provides partial amounts but not a verified Supplement Facts
panel. Keep amounts as tentative until label image/source confirms them.

Label facts:

- Brand: The Genius Brand
- Product name: Genius Pre
- Flavor/package: Blue Raspberry, 10.5 oz / 298 g
- User hint: `pre_workout`
- Serving size from secondary source: 1 scoop / 15 g
- Official active ingredient list:
  - Citrulline Malate
  - Beta Alanine
  - Betaine Nitrate / NO3T
  - AlphaGPC
  - Theobromine
  - AstraGin
  - Huperzine A
- Secondary source reports:
  - L-Citrulline Malate: 6 g
  - Beta-Alanine: 3 g
  - Alpha GPC: 600 mg
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
  - Alpha-GPC
  - Theobromine
  - AstraGin blend, likely product-level absorption blend unless the model needs
    Panax notoginseng / Astragalus components separately
  - Huperzine A
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

## Batch Notes

- Direct `curl` to iHerb currently returns a Cloudflare challenge, so extraction
  needs browser/search fallback or another reliable product-label source.
- Exa search can find official brand pages and secondary retailers for at least
  some products; prefer official brand pages when available.
- Product #12 has a user-supplied `pre_workout` hint and should become inactive
  inventory with a pre-workout product/substance context when encoded.
- Discontinued products can still be useful for the knowledge base, but their
  labels need extra source checking before YAML cards are created.
