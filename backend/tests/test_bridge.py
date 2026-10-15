import json

import pytest

import bridge as b


class Args:
    host = port = pipegen_topic = json_path = None


@pytest.fixture
def br(tmp_path, monkeypatch):
    """Bridge on a simulated 10 FPS clock: every on_raw() call is one frame, 100 ms apart."""
    monkeypatch.setenv("BRIDGE_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("K_FRAMES", "3")
    monkeypatch.setenv("COOLDOWN_S", "5")
    monkeypatch.setenv("CONFIRM_MIN_S", "0.5")
    clock = {"t": 1_000_000}
    monkeypatch.setattr(b, "now_ms", lambda: clock["t"])
    bridge = b.Bridge(b.Config(Args()))
    raw = bridge.on_raw

    def frame(payload):
        clock["t"] += 100
        return raw(payload)
    bridge.on_raw = frame
    return bridge


def full_schema(label="tapir", conf=0.8, tid="7"):
    return {"@timestamp": None, "sensor": {"id": "CAM_A"},
            "object": {"id": tid, label: {}, "confidence": conf,
                       "bbox": {"topleftx": 400, "toplefty": 300, "bottomrightx": 900, "bottomrighty": 800}}}


def test_full_schema_parses_label_from_key():
    objs, _ = b.extract_objects(full_schema(), 1920, 1080)
    assert b.normalise_class(objs[0]["label"]) == "tapir"
    assert objs[0]["camera_id"] == "CAM_A"


def test_minimal_schema():
    o = b.parse_minimal_object("12|100|200|300|400|Puma|#|0.77")
    assert o["label"] == "Puma" and o["confidence"] == 0.77 and o["bbox_xyxy"] == (100, 200, 300, 400)


def test_bbox_normalisation_pixels_and_normalised():
    assert b.normalise_bbox((960, 540, 1920, 1080), 1920, 1080) == [0.5, 0.5, 0.5, 0.5]
    assert b.normalise_bbox((0.1, 0.1, 0.3, 0.5), 1920, 1080) == [0.1, 0.1, 0.2, 0.4]


def test_k_frames_then_cooldown(br):
    out = []
    for _ in range(10):
        out += br.on_raw(full_schema())
    assert len(out) == 1                      # published once confirmed (>= 3 frames and >= 0.5 s), then cool-down
    e = out[0]
    assert e["class"] == "tapir" and e["class_id"] == 0 and e["track_id"] == 7
    assert len(json.dumps(e, separators=(",", ":"))) <= 256


def test_non_target_and_low_conf_dropped(br):
    for _ in range(5):
        assert br.on_raw({"objects": [{"label": "person", "confidence": 0.99, "bbox": [0, 0, 1, 1]}]}) == []
        assert br.on_raw({"objects": [{"label": "puma", "confidence": 0.2, "bbox": [0, 0, 1, 1]}]}) == []
    assert br.stats["veto_boxes"] == 5 and br.stats["dropped_low_conf"] == 5  # person = look-alike veto box


def test_road_zone(br):
    br.cfg.road_zone = (0.0, 0.6, 1.0, 1.0)   # lower 40 % of the frame is the road
    off_road = {"objects": [{"label": "puma", "confidence": 0.9, "bbox": [0.1, 0.0, 0.2, 0.2], "track_id": 1}]}
    on_road = {"objects": [{"label": "puma", "confidence": 0.9, "bbox": [0.1, 0.6, 0.2, 0.3], "track_id": 2}]}
    assert sum(len(br.on_raw(off_road)) for _ in range(10)) == 0
    assert sum(len(br.on_raw(on_road)) for _ in range(10)) == 1


def test_sensor_confirmation_flag(br):
    br.on_sensor({"armed": True})
    out = []
    for _ in range(8):
        out += br.on_raw({"objects": [{"class_id": 4, "score": 0.9, "bbox": [0.4, 0.5, 0.2, 0.3], "object_id": 21}]})
    assert out and out[0]["sensor_confirmed"] is True and out[0]["class"] == "giant_anteater"


def test_garbage_does_not_raise(br):
    for p in (None, 5, "x", [], {"objects": "nope"}, {"objects": [1, None, "a|b"]}, {"object": {}},
              {"objects": [{"label": "cat", "confidence": 0.9}]}, {"objects": [{"label": "dog", "bbox": "x"}]}):
        br.on_raw(p)


def test_replay_flag_propagates(br):
    out = []
    for _ in range(8):
        out += br.on_raw({"replay": True, "objects": [{"label": "tapir", "confidence": 0.9, "bbox": [0.1, 0.1, 0.2, 0.2], "track_id": 5}]})
    assert out and out[0]["replay"] is True
    assert br.status()["replay"] is True


def test_flicker_shorter_than_confirm_window_is_ignored(br):
    puma = {"objects": [{"label": "puma", "confidence": 0.9, "bbox": [0.1, 0.1, 0.2, 0.2], "track_id": 3}]}
    empty = {"objects": []}
    out = []
    for _ in range(3):           # 4-frame flicker (0.4 s), then gone long enough to reset the track
        out += sum((br.on_raw(puma) for _ in range(4)), [])
        out += sum((br.on_raw(empty) for _ in range(10)), [])
    assert out == []


def tapir(track=7, box=(0.30, 0.40, 0.20, 0.20)):
    return {"label": "tapir", "confidence": 0.8, "bbox": list(box), "track_id": track}


def test_look_alike_veto_suppresses_cat(br):
    cat = {"label": "cat", "confidence": 0.85, "bbox": [0.28, 0.38, 0.25, 0.25]}
    out = sum((br.on_raw({"objects": [tapir(), cat]}) for _ in range(20)), [])
    assert out == [] and br.stats["dropped_veto"] > 0


def test_weak_or_occasional_veto_does_not_block_real_animal(br):
    low_cat = {"label": "cat", "confidence": 0.3, "bbox": [0.28, 0.38, 0.25, 0.25]}       # below VETO_CONF
    out = sum((br.on_raw({"objects": [tapir(1), low_cat]}) for _ in range(10)), [])
    assert len(out) == 1
    dog = {"label": "dog", "confidence": 0.9, "bbox": [0.28, 0.38, 0.25, 0.25]}
    frames = [{"objects": [tapir(2), dog]} if i % 4 == 0 else {"objects": [tapir(2)]} for i in range(10)]  # 25 %
    assert len(sum((br.on_raw(f) for f in frames), [])) == 1


def test_veto_box_elsewhere_in_frame_is_ignored(br):
    person = {"label": "person", "confidence": 0.95, "bbox": [0.80, 0.10, 0.10, 0.40]}
    assert len(sum((br.on_raw({"objects": [tapir(), person]}) for _ in range(10)), [])) == 1


def test_full_schema_veto_object_is_recognised(br):
    """DeepStream full schema: one message per object, object type as a key, same frame @timestamp."""
    ts = "2026-10-15T12:00:00.000Z"
    box = {"topleftx": 400, "toplefty": 300, "bottomrightx": 900, "bottomrighty": 800}
    out = []
    for i in range(20):
        ts = f"2026-10-15T12:00:{i:02d}.000Z"
        out += br.on_raw({"@timestamp": ts, "object": {"id": "7", "puma": {}, "confidence": 0.9, "bbox": box}})
        out += br.on_raw({"@timestamp": ts, "object": {"id": "8", "cat": {}, "confidence": 0.9, "bbox": box}})
    assert br.stats["veto_boxes"] == 20
    assert out == [] and br.stats["dropped_veto"] > 0  # cat arrives AFTER the puma of the same frame
