from app.services.dedup import dedup_hash, merchant_key, normalize_description


def test_normalize_removes_accents_and_punctuation():
    assert normalize_description("SUPÉRMERCADO, XPTO!") == "supermercado xpto"


def test_merchant_key_strips_numbers():
    assert merchant_key("UBER *TRIP 12345") == "uber trip"
    assert merchant_key("PADARIA 001 - 2025") == "padaria"


def test_dedup_hash_stable_and_order_insensitive_to_formatting():
    h1 = dedup_hash("2025-03-05", 45.9, "A", "Uber *Trip")
    h2 = dedup_hash("2025-03-05", 45.90, "A", "UBER  *trip")
    assert h1 == h2


def test_dedup_hash_differs_on_amount():
    h1 = dedup_hash("2025-03-05", 45.90, "A", "Uber")
    h2 = dedup_hash("2025-03-05", 46.00, "A", "Uber")
    assert h1 != h2


def test_dedup_hash_differs_on_owner():
    assert dedup_hash("2025-03-05", 45.90, "A", "Uber") != dedup_hash(
        "2025-03-05", 45.90, "B", "Uber"
    )
