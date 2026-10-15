from wg_contract import CLASS_NAMES, effective_severity, normalise_class, validate_detection


def test_class_order_matches_training_labels():
    assert CLASS_NAMES == ["tapir", "jaguarundi", "maned_wolf", "puma", "giant_anteater"]


def test_normalise_class_aliases():
    assert normalise_class("Maned Wolf") == "maned_wolf"
    assert normalise_class("giantanteater") == "giant_anteater"
    assert normalise_class(3) == "puma"
    assert normalise_class("3") == "puma"
    assert normalise_class("person") is None
    assert normalise_class(9) is None


def test_sensor_fusion_severity():
    assert effective_severity("puma", True) == "HIGH"
    assert effective_severity("puma", False) == "LOW"
    assert effective_severity("tapir", True) == "CRITICAL"   # capped
    assert effective_severity("jaguarundi", False) == "WARN"  # floored
    assert effective_severity("capybara", True) == "WARN"


def test_validate_detection():
    ok = {"v": 1, "event_id": "wg-1", "class": "puma", "class_id": 3, "confidence": 0.8}
    assert validate_detection(ok) == []
    assert validate_detection({**ok, "extra": {"x": 1}}) == []
    assert validate_detection({**ok, "confidence": "high"})
    assert validate_detection({**ok, "confidence": 1.5})
    assert validate_detection({**ok, "v": 2})
    assert validate_detection({k: v for k, v in ok.items() if k != "event_id"})
    assert validate_detection([1, 2])
