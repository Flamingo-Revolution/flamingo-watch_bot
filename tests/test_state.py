from bot import state


def test_empty_schema_has_expected_keys():
    s = state.empty()
    assert set(s.keys()) == {"seen", "pending", "posted", "approved_queue", "failed", "daily"}


def test_load_missing_file_returns_empty(tmp_path):
    assert state.load(tmp_path / "nope.json") == state.empty()


def test_load_corrupt_json_returns_empty_not_raise(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert state.load(p) == state.empty()


def test_load_non_dict_json_returns_empty(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert state.load(p) == state.empty()


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "sub" / "state.json"  # parent dir doesn't exist yet
    s = state.empty()
    state.mark_seen(s, "a")
    state.mark_seen(s, "b")
    state.save(p, s)
    assert state.load(p)["seen"] == ["a", "b"]


def test_mark_seen_is_idempotent():
    s = state.empty()
    state.mark_seen(s, "a")
    state.mark_seen(s, "a")
    assert s["seen"] == ["a"]


def test_seen_list_is_capped_dropping_oldest():
    s = state.empty()
    for i in range(state.SEEN_CAP + 50):
        state.mark_seen(s, f"key-{i}")
    assert len(s["seen"]) == state.SEEN_CAP
    assert s["seen"][0] == "key-50"
    assert s["seen"][-1] == f"key-{state.SEEN_CAP + 49}"


def test_save_is_atomic_leaves_no_tmp_files(tmp_path):
    state.save(tmp_path / "state.json", state.empty())
    assert list(tmp_path.glob(".state-*")) == []


def test_is_seen():
    s = state.empty()
    state.mark_seen(s, "a")
    assert state.is_seen(s, "a")
    assert not state.is_seen(s, "b")
