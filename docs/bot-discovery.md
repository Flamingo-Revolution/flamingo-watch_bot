# Bot discovery (Phase 0)

Findings for the Flamingo Watch → Discord → Instagram automation (see this repo's `CLAUDE.md`
copy / the owner's working doc). No feature code in this phase — this document only.

All file references below (`app/export.py`, `app/feed.py`, `app/static/...`) point into the
**`Flamingo-Revolution`** repo, which is read-only reference material for this project — nothing
in this document was copied or committed from that repo, only observed.

## 1. What `app/export.py` writes

The static export (`python -m app.export`, run by the owner's PC via `publish-loop.sh`, see
`Flamingo-Revolution/STATIC-HOSTING.md`) writes, under the exported site root:

| Path | Content |
|---|---|
| `/feed.xml`, `/sq/feed.xml` | RSS, latest 50 articles (not grouped by story), per language |
| `/digest.xml`, `/sq/digest.xml` | RSS digest (not evaluated further — out of scope, not a per-story feed) |
| `/data/articles-en.json`, `/data/articles-sq.json` | **Story groups, last 7 days**, per language |
| `/data/articles-en-30d.json`, `/data/articles-sq-30d.json` | Same, last 30 days |
| `/data/stats.json` | Site-wide counters, not story data |
| `/data/rnbbnb-{lang}.json` | Unrelated feature (an accusation meter), not used by the bot |
| `/data/version.json` | `{content_hash, exported_at}` — last export timestamp, useful for alerting if the site goes stale |

The JSON files are built by `export._articles_json()` → `feed.query_groups()`
(`Flamingo-Revolution/app/export.py:62-68`, `Flamingo-Revolution/app/feed.py:64-131`):
articles sharing a `story_key` (set by the AI step in `fetcher.py`/`ai.py`, not re-verified here)
are grouped; `group["key"]` is the story key, `group["articles"]` is every outlet's article for
that story, **newest first** (`articles[0]` is the lead/most recent). Each article is "slimmed" to
`id, url, source, published_at, lang, title, summary, tags, ai` (+ `original_title` only when it
differs from the translated `title`).

Confirmed in `app/feed.py:article_dict()`: `title`/`summary` are already in the **file's own
language** (an EN file never contains an Albanian title), AI-translated when
`ai_status == "done"` (`ai: true`), otherwise falls back to the original-language title with no
summary.

## 2. Live site: `curl` results (2026-10-01)

All four endpoints are live and match the file list above:

| URL | Status | Content-Type | Notes |
|---|---|---|---|
| `https://flamingo-watch.com/feed.xml` | 200 | `application/rss+xml; charset=utf-8` | 50 `<item>`s |
| `https://flamingo-watch.com/sq/feed.xml` | 200 | `application/rss+xml; charset=utf-8` | 50 `<item>`s, Albanian |
| `https://flamingo-watch.com/data/articles-en.json` | 200 | `application/json` | 340 groups (at check time) |
| `https://flamingo-watch.com/data/articles-sq.json` | 200 | `application/json` | 340 groups, **same 340 keys as the EN file** |
| `https://flamingo-watch.com/data/version.json` | 200 | `application/json` | `{"content_hash":"df6c8a868fcd95d9","exported_at":"2026-10-01T15:42:03Z"}` |
| `https://flamingo-watch.com/api/articles?lang=en` | **404** | — | confirms README note: dynamic API is server-mode only, not on the static export |

**`feed.xml`, first item (verbatim):**
```xml
<title>Why is the Democratic Party opposing Ursula Von der Leyen?!</title>
<link>https://javanews.al/pse-pd-po-i-kundervihet-ursula-von-der-leyen</link>
<guid isPermaLink="false">flamingo-watch-605</guid>
<description>Democratic Party representatives Gazment Bardhi and Saimir Korreshi opposed
positions of European Commission President Ursula Von der Leyen during a conference of
parliamentary leaders.</description>
<source url="https://javanews.al/pse-pd-po-i-kundervihet-ursula-von-der-leyen">JavaNews</source>
<pubDate>Thu, 01 Oct 2026 15:35:08 +0000</pubDate>
```

**`feed.xml`, second item (verbatim):**
```xml
<title>Over 2,000 residents without urban transport in the Pyjore area near Zvërnec</title>
<link>https://euronews.al/mbi-2-mije-banore-pa-transport-urban-ne-zonen-e-pyjores-prane-zvernecit</link>
<guid isPermaLink="false">flamingo-watch-601</guid>
<description>Residents in Vlorë's Pyjore area lack urban transport; buses stop at the old
Caustic Soda facility and do not continue toward Narta and Zvërnec, forcing residents to walk
hundreds of meters.</description>
<source url="https://euronews.al/...">Euronews Albania</source>
<pubDate>Thu, 01 Oct 2026 15:03:51 +0000</pubDate>
```

**`<source>` confirmed to be the original outlet** (JavaNews, Euronews Albania — not
"Flamingo Watch"), as required by the hard constraint in the owner's spec (source credit).

**`data/articles-en.json`, first group (verbatim, truncated):**
```json
{
  "key": "pd-von-der-leyen-opposition",
  "slug": null,
  "articles": [{
    "id": 605,
    "url": "https://javanews.al/pse-pd-po-i-kundervihet-ursula-von-der-leyen",
    "source": "JavaNews",
    "published_at": "2026-10-01T15:35:08Z",
    "lang": "sq",
    "title": "Why is the Democratic Party opposing Ursula Von der Leyen?!",
    "summary": "Democratic Party representatives Gazment Bardhi and Saimir Korreshi opposed positions of European Commission President Ursula Von der Leyen during a conference of parliamentary leaders.",
    "tags": ["opposition", "international-reaction"],
    "ai": true,
    "original_title": "Pse PD po i kundërvihet Ursula Von der Leyen?!"
  }]
}
```
(`lang` inside the article is the *source* article's original language — `sq` here even though
this is the EN file, because `title`/`summary` were AI-translated to English. Don't key off this
field; the file itself tells you the card language.)

**Multi-source grouping confirmed**: 76 of 340 groups in the EN file have >1 article (one story,
several outlets), e.g. `rama-criminal-procedure-code-criticism` has 3 articles from Citizens
Channel, Vizion Plus, Reporter.al, ordered newest → oldest. `slug` is only set when a group has
≥2 sources (`STORY_MIN_SOURCES`); single-source groups have `slug: null`. Not needed for our
dedup key (we use `key`), just noted so it isn't mistaken for a missing-data bug.

**Group order**: top-level `groups` array is newest-lead-article-first (confirmed: group 0's
lead `published_at` is later than group 1's). The bot must reverse this before applying
`MAX_PER_RUN`/oldest-first.

## 3. Source of truth and field mapping

**Decision: `/data/articles-{lang}.json` is the source of truth, not RSS.** Justification:
- RSS is flat (no story grouping — each outlet's coverage of the same story is a separate
  `<item>`), capped at 50 items, and carries no story key.
- The JSON already groups by `story_key`, in both languages, under the same keys (340/340 overlap
  confirmed above) — exactly what's needed to dedupe a story once even when multiple outlets
  cover it.
- `FEED_URL` becomes a comma-separated list of JSON URLs as the fallback chain, e.g.
  `https://flamingo-watch.com/data/articles-{lang}.json` with `{lang}` substituted from
  `CARD_LANG` — `bot/feed.py` fetches the one file matching the configured language, not both.

| `Story` field | Source |
|---|---|
| `key` | group `key` |
| `title` | `group.articles[0].title` (lead article, already in the file's language) |
| `summary` | `group.articles[0].summary` (may be `None` if `ai` is `false` — card must omit the summary block) |
| `source` | `group.articles[0].source` |
| `url` | `group.articles[0].url` |
| `published` | `group.articles[0].published_at` |
| `lang` | the file's language (`en`/`sq`), not the article's own `lang` field |

`bot/feed.py` parses this with stdlib `json` (not `xml.etree`, since we're using the JSON source,
not RSS). Keep `FEED_URL` support for a comma-separated fallback list, in case the JSON endpoint
ever goes down and RSS is needed as a manual override.

## 4. Fonts

The site repo ships **`.woff2` only** — `app/static/fonts/{Anton,IBMPlexSans}-*.woff2` — which
Pillow cannot load (needs TTF/OTF). No TTF/OTF exists anywhere in that repo.

Both families are Google Fonts under the **SIL Open Font License (OFL)**, which permits bundling
and redistribution. Plan for Phase 1: download the official TTF releases of `Anton-Regular`,
`IBMPlexSans-Regular`, and `IBMPlexSans-SemiBold` and commit them to `bot/fonts/` in *this* repo.
Albanian glyph coverage (`ë ç Ë Ç`) needs a runtime check once the actual TTFs are in hand (render
a test string and diff against expected glyphs) — both families are known to support Latin
Extended-A, which includes these, but this gets a real assertion in `tests/test_card.py` rather
than taken on faith. Fallback if a glyph is missing: bundle `DejaVuSans.ttf`/`DejaVuSans-Bold.ttf`
instead (also OFL-compatible, redistributable).

## 5. Existing workflows, Python version, dependencies

- This repo (`flamingo-watch_bot`) is brand new: just a `README.md`, no workflows, no code. No
  collision risk for `.github/workflows/ig-cards.yml` etc.
- Python version: **3.12**, matched to `Flamingo-Revolution/Dockerfile`
  (`FROM python:3.12-slim`) for consistency. This repo has no Dockerfile of its own — bot
  workflows pin `actions/setup-python@v5` to `3.12` directly.
- No `requirements.txt` exists yet in this repo. `httpx` and `Pillow` both need to be added
  fresh (the site repo's `httpx==0.28.*` pin is a reasonable version to match, but this repo
  doesn't inherit it automatically — it's a separate `requirements.txt`).

## 6. Open questions for the owner (not blocking Phase 1 start)

1. **Hashtag list** for `HASHTAGS` — default `#Albania #FlamingoRevolution` unless you want
   something else.
2. **Discord user IDs** for `PERMITTED_VOTERS` (required from Phase 2) and `ADMIN_VOTERS`
   (optional) — these go directly into this repo's GitHub repo variables (Settings → Secrets and
   variables → Actions → Variables), never pasted here or committed.

Neither blocks Phase 1 (webhook-only posting, no voting yet), so Phase 1 can start now with
defaults; these are only needed before Phase 2.
