from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from bot import card
from bot.feed import Story


def _story(**overrides):
    base = dict(
        key="k", title="Rama takon ambasadorët e BE", summary="Një përmbledhje e shkurtër.",
        source="JavaNews", url="https://javanews.al/x", published="2026-10-01T10:00:00Z", lang="sq",
    )
    base.update(overrides)
    return Story(**base)


def test_render_is_1080x1350_jpeg_under_8mb():
    data = card.render(_story(), "sq")
    img = Image.open(BytesIO(data))
    assert img.format == "JPEG"
    assert img.size == (1080, 1350)
    assert len(data) < 8 * 1024 * 1024


def test_render_albanian_characters_do_not_raise():
    s = _story(title="Është çështje e madhe në Shqipëri", summary="Çmimet u rritën në Tiranë.")
    card.render(s, "sq")  # must not raise


def test_render_without_summary_omits_block_without_raising():
    s = _story(summary=None)
    card.render(s, "sq")  # must not raise


def test_render_worst_case_max_lines_still_fits_canvas():
    s = _story(title=" ".join(["fjalë"] * 60), summary=" ".join(["përshkrim"] * 120))
    data = card.render(s, "sq")
    img = Image.open(BytesIO(data))
    assert img.size == (1080, 1350)


def test_wrap_never_exceeds_measured_width():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = card._font(card.PLEX_REGULAR, 38)
    text = " ".join(["fjalëformim"] * 30)
    lines = card._wrap(draw, text, font, max_width=900, max_lines=8)
    assert lines  # produced something
    for line in lines:
        assert draw.textlength(line, font=font) <= 900


def test_wrap_adds_ellipsis_only_when_actually_truncated():
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font = card._font(card.PLEX_REGULAR, 38)

    long_text = " ".join(["word"] * 100)
    truncated = card._wrap(draw, long_text, font, max_width=900, max_lines=3)
    assert len(truncated) == 3
    assert truncated[-1].endswith("…")

    short_text = "just a few words"
    fits = card._wrap(draw, short_text, font, max_width=900, max_lines=3)
    assert not fits[-1].endswith("…")


def test_missing_bundled_font_raises_instead_of_silent_fallback(tmp_path):
    with pytest.raises(Exception):
        card._font(tmp_path / "does-not-exist.ttf", 40)
