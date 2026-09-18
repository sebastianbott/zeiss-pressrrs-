#!/usr/bin/env python3
"""
Erzeugt eine RSS-Feed-Datei (docs/feed.xml) aus den ZEISS Pressemitteilungen.

Die Seite lädt ihre Ergebnisliste per JavaScript aus einer internen
Mindbreeze-Such-API nach (nicht als einfacher HTML-Inhalt vorhanden).
Deshalb wird hier ein echter (headless) Browser via Playwright benutzt,
der die Seite genauso rendert wie ein normaler Besucher, wartet, bis die
Ergebnisliste geladen ist, und die einzelnen Pressemitteilungen ausliest.

Falls ZEISS die Struktur der Seite ändert, muss ggf. nur die Funktion
`extract_items()` unten angepasst werden (Selektoren prüfen: Seite im
eigenen Chrome öffnen -> Rechtsklick auf eine Pressemitteilung ->
"Untersuchen").
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

SOURCE_URL = "https://www.zeiss.com/corporate/en/about-zeiss/present/newsroom/press-releases.html"
SITE_URL = "https://www.zeiss.com/corporate/en/about-zeiss/present/newsroom.html"
OUTPUT_PATH = Path(__file__).parent / "docs" / "feed.xml"
FEED_TITLE = "ZEISS Press Releases"
FEED_DESCRIPTION = "Automatisch erzeugter RSS-Feed aus den ZEISS Pressemitteilungen."
MAX_ITEMS = 50

# Mögliche CSS-Selektoren für eine einzelne Ergebnis-Karte im
# Mindbreeze Content Hub. Es wird der erste Selektor genommen, der
# mindestens einen Treffer liefert (defensiv, weil das gerenderte DOM
# hier nicht getestet werden konnte).
CARD_SELECTOR_CANDIDATES = [
    '[data-js-select="MindBreezeContentHub__app"] article',
    '[data-js-select="MindBreezeContentHub__app"] li',
    '[data-js-select="MindBreezeContentHub__app"] [class*="result"]',
    '[data-js-select="MindBreezeContentHub__app"] [class*="card"]',
    '.mindbreeze-content-hub article',
    '.mindbreeze-content-hub li',
    '.mindbreeze-content-hub [class*="result"]',
    '.mindbreeze-content-hub [class*="card"]',
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def extract_items(page) -> list[dict]:
    """Sucht die Ergebnis-Container im gerenderten DOM und liest
    Titel, Link, Datum und Teaser-Text aus jedem einzelnen aus."""

    app_selector = '[data-js-select="MindBreezeContentHub__app"]'
    page.wait_for_selector(app_selector, timeout=30_000)

    # Warten, bis mindestens ein Link innerhalb des App-Containers
    # erscheint (Indiz, dass die Ergebnisse nachgeladen wurden).
    try:
        page.wait_for_function(
            """(sel) => {
                const root = document.querySelector(sel);
                return root && root.querySelectorAll('a[href]').length > 3;
            }""",
            arg=app_selector,
            timeout=30_000,
        )
    except PlaywrightTimeoutError:
        log("Warnung: Ergebnisliste hat nicht innerhalb von 30s reagiert.")

    # Zusätzliche Wartezeit für Nachlade-Effekte / Animationen.
    page.wait_for_timeout(1500)

    items: list[dict] = []
    used_selector = None

    for selector in CARD_SELECTOR_CANDIDATES:
        cards = page.query_selector_all(selector)
        if len(cards) >= 2:
            used_selector = selector
            break

    if used_selector is None:
        # Fallback: alle Links im App-Container, die auf eine
        # Unterseite (nicht auf # oder javascript:) verweisen, und
        # genug sichtbaren Text als Titel haben.
        log("Kein Karten-Selektor hat gegriffen, nutze Link-Fallback.")
        links = page.query_selector_all(f'{app_selector} a[href]')
        seen_urls = set()
        for a in links:
            href = a.get_attribute("href") or ""
            text = (a.inner_text() or "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            if len(text) < 8:
                continue
            url = urljoin(SOURCE_URL, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({"title": text, "url": url, "date": None, "summary": ""})
        return items[:MAX_ITEMS]

    log(f"Verwende Selektor: {used_selector} ({len(page.query_selector_all(used_selector))} Treffer)")

    for card in page.query_selector_all(used_selector):
        link_el = card.query_selector("a[href]")
        if link_el is None:
            continue
        href = link_el.get_attribute("href") or ""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        url = urljoin(SOURCE_URL, href)

        title_el = (
            card.query_selector("h1, h2, h3, h4")
            or card.query_selector('[class*="title"]')
            or link_el
        )
        title = (title_el.inner_text() or "").strip() if title_el else ""
        if not title:
            title = (link_el.inner_text() or "").strip()
        if not title:
            continue

        date_el = card.query_selector("time") or card.query_selector('[class*="date"]')
        date_text = None
        if date_el is not None:
            date_text = date_el.get_attribute("datetime") or (date_el.inner_text() or "").strip()

        summary_el = card.query_selector("p") or card.query_selector('[class*="teaser"], [class*="text"]')
        summary = (summary_el.inner_text() or "").strip() if summary_el else ""

        items.append({"title": title, "url": url, "date": date_text, "summary": summary})

    return items[:MAX_ITEMS]


def parse_date(date_text: str | None) -> datetime:
    if date_text:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y"):
            try:
                dt = datetime.strptime(date_text[: len(fmt) + 10].strip(), fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def build_rss(items: list[dict]) -> str:
    now = format_datetime(datetime.now(timezone.utc))
    rss_items = []
    for it in items:
        guid = hashlib.sha1(it["url"].encode("utf-8")).hexdigest()
        pub_date = format_datetime(parse_date(it.get("date")))
        rss_items.append(
            f"""    <item>
      <title>{escape(it['title'])}</title>
      <link>{escape(it['url'])}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(it.get('summary') or '')}</description>
    </item>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape(FEED_TITLE)}</title>
    <link>{escape(SOURCE_URL)}</link>
    <description>{escape(FEED_DESCRIPTION)}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(rss_items)}
  </channel>
</rss>
"""


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ))
        log(f"Lade {SOURCE_URL} ...")
        page.goto(SOURCE_URL, wait_until="networkidle", timeout=60_000)
        items = extract_items(page)
        browser.close()

    if not items:
        log("FEHLER: Keine Pressemitteilungen gefunden. Selektoren in scrape.py prüfen.")
        return 1

    log(f"{len(items)} Pressemitteilungen gefunden.")
    rss = build_rss(items)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rss, encoding="utf-8")
    log(f"Geschrieben nach {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
