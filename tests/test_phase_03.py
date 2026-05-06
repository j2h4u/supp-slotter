from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

OPERATOR_USAGE_NOT_PRODUCT_AMOUNT = {
    "magnesium_glycinate": "200 mg × 2/day (= 400 mg elemental Mg)",
    "tadalafil": "1.25 mg",
}


def load_yaml(path: str) -> object:
    return yaml.safe_load((ROOT / path).read_text())


def load_cards(directory: str) -> dict[str, dict]:
    return {
        path.stem: yaml.safe_load(path.read_text())
        for path in sorted((ROOT / directory).glob("*.yaml"))
    }


def product_text(product: dict) -> str:
    return yaml.safe_dump(product, sort_keys=False, allow_unicode=True)


def test_known_inventory_brands_are_complete_on_product_cards() -> None:
    inventory = load_yaml("data/inventory.yaml")["supplements"]
    products = load_cards("data/products")

    expected_brands = {
        item_id: entry["brand"]
        for item_id, entry in inventory.items()
        if entry.get("brand") and entry["brand"] != "unknown"
    }

    assert expected_brands
    assert {
        item_id: products[entry["product"]].get("brand")
        for item_id, entry in inventory.items()
        if item_id in expected_brands
    } == expected_brands
    assert all(product.get("brand") != "unknown" for product in products.values())


def test_inventory_dose_and_notes_are_routed_before_strip() -> None:
    inventory = load_yaml("data/inventory.yaml")["supplements"]
    products = load_cards("data/products")

    for item_id, entry in inventory.items():
        product = products[entry["product"]]
        serialized = product_text(product)
        if item_id in OPERATOR_USAGE_NOT_PRODUCT_AMOUNT:
            assert OPERATOR_USAGE_NOT_PRODUCT_AMOUNT[item_id] in entry.get("notes", "")
            assert OPERATOR_USAGE_NOT_PRODUCT_AMOUNT[item_id] not in serialized
            continue

        dose = entry.get("dose")
        if dose:
            assert dose in serialized

        notes = entry.get("notes")
        if notes and item_id not in {"tadalafil", "lions_mane"}:
            assert notes in serialized


def test_ambiguous_product_amounts_are_not_fabricated() -> None:
    products = load_cards("data/products")

    electrolyte = products["electrolyte_caps"]
    assert electrolyte["brand"] == "TiM"
    assert "1 g/cap" in product_text(electrolyte)
    assert all("amount" not in component for component in electrolyte["components"])

    trace_minerals = products["trace_minerals"]
    assert trace_minerals["brand"] == "Life Extension"
    assert "per-cap weights not enumerated" in product_text(trace_minerals)
    assert all("amount" not in component for component in trace_minerals["components"])

    coenzyme = products["coenzyme_b_complex"]
    assert coenzyme["brand"] == "Country Life"
    assert "dose per cap not labelled granularly" in product_text(coenzyme)
    assert all("amount" not in component for component in coenzyme["components"])
