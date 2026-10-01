from bot import caption


def test_basic_caption_shape():
    text = caption.build("Title here", "A short summary.", "Outlet", "https://x.example/y",
                          "#Albania #FlamingoRevolution")
    assert text.startswith("Title here\n\nA short summary.")
    assert "Source: Outlet\nhttps://x.example/y" in text
    assert "Automated summary, check the original." in text
    assert text.endswith("#Albania #FlamingoRevolution")


def test_empty_summary_skipped_cleanly():
    text = caption.build("Title", None, "Outlet", "https://x.example", "")
    assert "\n\n\n" not in text
    assert text.startswith("Title\n\nSource: Outlet")


def test_albanian_characters_preserved():
    text = caption.build("Është lajm", "Çmimet u rritën në Tiranë.", "Gazeta", "https://x.example", "")
    assert "Është lajm" in text
    assert "Çmimet u rritën në Tiranë." in text


def test_over_length_summary_is_truncated_other_parts_kept_intact():
    long_summary = "fjalë " * 1000
    text = caption.build("Title", long_summary, "Outlet Name", "https://x.example/url",
                          "#Albania #FlamingoRevolution")
    assert len(text) <= caption.MAX_CAPTION
    assert "Source: Outlet Name\nhttps://x.example/url" in text
    assert "Automated summary, check the original." in text
    assert text.endswith("#Albania #FlamingoRevolution")
    assert "…" in text


def test_short_caption_is_not_truncated():
    text = caption.build("T", "S", "O", "https://x", "#h")
    assert "…" not in text
