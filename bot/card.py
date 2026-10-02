"""Render a Flamingo Watch story as a 1080x1350 JPEG card for Discord/Instagram.

Visual language ported from the live site's own share-image generator
(Flamingo-Revolution/app/static/js/share-image.js, canvas-based, 1080x1920) and the
owner-supplied flamingo+F mark (bot/assets/flamingo-mark.png), adapted to the 4:5
Instagram feed ratio. See docs/bot-discovery.md and CLAUDE.md section 5.
"""
from __future__ import annotations

import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .feed import Story

W, H = 1080, 1350
PAD = 80

BG = (10, 10, 10)           # #0A0A0A
GRID = (21, 21, 21)         # #2A2A2A blended at ~35% alpha over BG, precomputed flat
PINK = (255, 62, 165)       # #FF3EA5
TEXT = (245, 245, 240)      # #F5F5F0
MUTED = (154, 154, 148)     # #9A9A94
SOFT = (216, 216, 210)      # #D8D8D2

ASSETS_DIR = Path(__file__).parent / "assets"
FONTS_DIR = Path(__file__).parent / "fonts"

LOGO_PATH = ASSETS_DIR / "flamingo-mark.png"
ANTON = FONTS_DIR / "Anton-Regular.ttf"
PLEX_REGULAR = FONTS_DIR / "IBMPlexSans-Regular.ttf"
PLEX_SEMIBOLD = FONTS_DIR / "IBMPlexSans-SemiBold.ttf"
PLEX_BOLD = FONTS_DIR / "IBMPlexSans-Bold.ttf"

SITE_TAPE_TEXT = "FLAMINGO-WATCH.COM"

TITLE_MAX_LINES = 6
SUMMARY_MAX_LINES = 8


@lru_cache(maxsize=None)
def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    # Intentionally not wrapped in try/except: a missing bundled font must raise,
    # never silently fall back to Pillow's bitmap default (CLAUDE.md section 5).
    # Cached: a single render loads each (font, size) pair at most once instead of
    # re-reading the TTF from disk for every card in a batch.
    return ImageFont.truetype(str(path), size)


def _fit_word(draw: ImageDraw.ImageDraw, word: str, font: ImageFont.FreeTypeFont,
              max_width: int) -> str:
    """A single word wider than max_width on its own (e.g. a raw URL or an
    unbroken compound in AI-generated text we don't fully control) would otherwise
    overflow the card uncut, since _wrap only breaks on whitespace. Trim it to fit,
    same character-trim-with-ellipsis technique as the last-line truncation below."""
    if draw.textlength(word, font=font) <= max_width:
        return word
    trimmed = word
    while trimmed and draw.textlength(trimmed + "…", font=font) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + "…") if trimmed else word[:1]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_width: int, max_lines: int) -> list[str]:
    """Word-wrap by measured width (never fixed character counts). Ports the same
    algorithm the live site uses in share-image.js's wrap(), so truncation behaves
    identically: '...' is added only when a line was actually cut off."""
    words = [w for w in re.split(r"\s+", text or "") if w]
    words = [_fit_word(draw, w, font, max_width) for w in words]
    lines: list[str] = []
    line = ""
    for w in words:
        test = f"{line} {w}" if line else w
        if draw.textlength(test, font=font) <= max_width:
            line = test
            continue
        if line:
            lines.append(line)
        line = w
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and line:
        lines.append(line)
    if len(lines) == max_lines and " ".join(words) != " ".join(lines):
        last = lines[max_lines - 1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[max_lines - 1] = re.sub(r"[\s,.;:]+$", "", last) + "…"
    return lines


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], x: int, y: int,
                 font: ImageFont.FreeTypeFont, fill, line_height: int) -> int:
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=fill)
    return y + len(lines) * line_height


def _background(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([0, 0, W, H], fill=BG)
    for x in range(0, W + 1, 72):
        draw.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H + 1, 72):
        draw.line([(0, y), (W, y)], fill=GRID, width=1)
    draw.rectangle([0, 0, W, 12], fill=PINK)  # top accent bar


def _header(img: Image.Image, draw: ImageDraw.ImageDraw, kicker: str) -> None:
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo_h = 72
    logo_w = round(logo.width * logo_h / logo.height)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
    logo_y = 32
    img.paste(logo, (PAD, logo_y), logo)

    font = _font(ANTON, 46)
    text_x = PAD + logo_w + 22
    # Vertically center "FLAMINGO WATCH" against the logo mark.
    bbox = draw.textbbox((0, 0), "FLAMINGO WATCH", font=font)
    text_h = bbox[3] - bbox[1]
    text_y = logo_y + (logo_h - text_h) / 2 - bbox[1]
    draw.text((text_x, text_y), "FLAMINGO WATCH", font=font, fill=PINK)

    kicker_font = _font(PLEX_SEMIBOLD, 22)
    draw.text((text_x, logo_y + logo_h + 4), kicker.upper(), font=kicker_font, fill=MUTED)


def _ribbon() -> Image.Image:
    """Diagonal pink tape reading FLAMINGO-WATCH.COM, same technique as the site's
    footer(): drawn flat on its own layer, then rotated and composited."""
    height = 70
    extra = 160
    layer_w = W + extra
    layer = Image.new("RGBA", (layer_w, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 0, layer_w, height], fill=PINK)
    font = _font(ANTON, 34)
    bbox = d.textbbox((0, 0), SITE_TAPE_TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((layer_w - tw) / 2 - bbox[0], (height - th) / 2 - bbox[1]), SITE_TAPE_TEXT,
           font=font, fill=BG)
    return layer.rotate(-2, expand=True, resample=Image.BICUBIC)


def render(story: Story, lang: str) -> bytes:
    """Render `story` as a 1080x1350 JPEG card. `lang` is accepted separately from
    `story.lang` so a future bilingual carousel can render the same story twice with
    different language labels (CLAUDE.md section 1b) -- today they're always equal."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    _background(draw)
    _header(img, draw, kicker="Albania · Live News Monitor" if lang != "sq" else "Shqipëri · Monitorim i Lajmeve")

    title_font = _font(PLEX_SEMIBOLD, 66)
    title_line_h = 76
    title_lines = _wrap(draw, story.title, title_font, W - PAD * 2, TITLE_MAX_LINES)

    summary_font = _font(PLEX_REGULAR, 38)
    summary_line_h = 46
    summary_lines = (_wrap(draw, story.summary, summary_font, W - PAD * 2, SUMMARY_MAX_LINES)
                      if story.summary else [])

    source_font = _font(PLEX_BOLD, 32)
    source_text = f"Source: {story.source}"
    source_bbox = draw.textbbox((0, 0), source_text, font=source_font)
    source_h = source_bbox[3] - source_bbox[1]
    compliance_h = source_h

    # Title + divider + summary + compliance block, as a single unit. Short stories
    # (no AI summary, common -- see docs/bot-discovery.md) would otherwise leave a
    # dead gap either above or below; instead the whole unit is positioned in the
    # header-to-ribbon zone, weighted toward the top so headlines still read like
    # headlines rather than sitting dead center.
    DIVIDER_H = 24 + 8 + 40
    CONTENT_TO_COMPLIANCE_GAP = 40
    content_h = len(title_lines) * title_line_h + DIVIDER_H + len(summary_lines) * summary_line_h
    block_h = content_h + CONTENT_TO_COMPLIANCE_GAP + compliance_h

    zone_top = 150
    ribbon_y = H - 150
    zone_bottom = ribbon_y - 28  # fixed gap above the ribbon
    slack = max(0, (zone_bottom - zone_top) - block_h)
    y = zone_top + round(slack * 0.35)

    y = _draw_lines(draw, title_lines, PAD, y, title_font, TEXT, line_height=title_line_h)
    y += 24
    draw.rectangle([PAD, y, PAD + 120, y + 8], fill=PINK)
    y += 40
    if summary_lines:
        _draw_lines(draw, summary_lines, PAD, y, summary_font, SOFT, line_height=summary_line_h)

    # Source credit: plain, horizontal, never rotated into the ribbon. Anchored to the
    # fixed zone_bottom, not to the content above, so its position (and the ribbon's)
    # never moves regardless of how short or long the story is.
    source_y = zone_bottom - source_h
    draw.text((PAD, source_y), source_text, font=source_font, fill=TEXT)

    ribbon = _ribbon()
    ribbon_x = (W - ribbon.width) // 2
    img.paste(ribbon, (ribbon_x, ribbon_y), ribbon)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
