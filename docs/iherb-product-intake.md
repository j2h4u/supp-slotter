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

## Batch Notes

- Direct `curl` to iHerb currently returns a Cloudflare challenge, so extraction
  needs browser/search fallback or another reliable product-label source.
- Exa search can find official brand pages and secondary retailers for at least
  some products; prefer official brand pages when available.
- Product #12 has a user-supplied `pre_workout` hint and should become inactive
  inventory with a pre-workout product/substance context when encoded.
- Discontinued products can still be useful for the knowledge base, but their
  labels need extra source checking before YAML cards are created.
