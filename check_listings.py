#!/usr/bin/env python3
"""
Boulder housing checker.

Runs on a schedule (via GitHub Actions), checks a few rental listing sites for
studios and 1-bedrooms in Boulder under the rent ceiling, and writes an HTML
page (docs/index.html) served by GitHub Pages. New listings since the last run
are flagged.

Geographic scope: all of Boulder city, which is roughly everything within ~5
miles of the East Boulder office at 2000 Central Ave. There is no reliable way
to scrape a true radius, so we cover Boulder-wide and use a ZIP guardrail to
keep results inside the ~5-mile zone.

No notifications, no API keys. Just a webpage you bookmark and check.

Sites checked:
  - Apartment List  (most scrape-tolerant; primary source)
  - Zillow          (may get blocked; best-effort)
  - Apartments.com  (may get blocked; best-effort)
"""

import json
import os
import re
import sys
import time
import html
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Search criteria  --  edit these if your needs change
# ---------------------------------------------------------------------------
MAX_RENT = 1750          # hard ceiling
IDEAL_RENT = 1500        # listings at or under this get a star
MAX_BEDS = 1             # studio (0) or 1BR only; bump to 2 to include 2BRs

# ZIP guardrail: only keep listings whose ZIP is one of these (when a ZIP is
# detectable in the listing). This is how we approximate "within ~5 miles of
# the East Boulder office." These are the Boulder-area ZIPs inside that radius:
#   80301 = east Boulder / Gunbarrel        80304 = north Boulder
#   80302 = central / west Boulder          80305 = south Boulder / Table Mesa
#   80303 = southeast Boulder               80503 = north Gunbarrel / Niwot edge
# Louisville (80027) sits just past 5 miles -- add it here if you want it included.
ALLOWED_ZIPS = {"80301", "80302", "80303", "80304", "80305", "80503"}

# Files
ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
SEEN_FILE = ROOT / "seen_listings.json"
OUTPUT_HTML = DOCS / "index.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_rent(text):
    """First dollar amount in a string -> int, or None."""
    if not text:
        return None
    m = re.search(r"\$\s*([\d,]+)", text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_beds(text):
    """Bedroom count from card text. 0 = studio, int = N beds, None = unknown."""
    if not text:
        return None
    t = text.lower()
    if "studio" in t:
        return 0
    m = re.search(r"(\d+)\s*(?:beds?|bds?|br\b)", t)
    if m:
        return int(m.group(1))
    return None


def parse_zip(text):
    """First Colorado 80xxx ZIP in the text, or None."""
    if not text:
        return None
    m = re.search(r"\b(80\d{3})\b", text)
    return m.group(1) if m else None


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        return r.status_code, r.text
    except Exception as e:
        print(f"  ! request failed: {e}", file=sys.stderr)
        return None, None


def load_seen():
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))


def make_listing(title, url, source):
    return {
        "id": url,
        "title": title[:120],
        "rent": parse_rent(title),
        "beds": parse_beds(title),
        "zip": parse_zip(title),
        "url": url,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Site scrapers -- each returns a list of listing dicts.
# ---------------------------------------------------------------------------
def scrape_apartmentlist():
    listings = []
    url = "https://www.apartmentlist.com/co/boulder"
    print(f"[apartmentlist] fetching {url}")
    status, body = fetch(url)
    if status != 200 or not body:
        print(f"[apartmentlist] skipped (status={status})")
        return listings
    soup = BeautifulSoup(body, "html.parser")
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/co/boulder/" not in href:
            continue
        text = a.get_text(" ", strip=True)
        if parse_rent(text) is None:
            continue
        full = href if href.startswith("http") else f"https://www.apartmentlist.com{href}"
        if full in seen_urls:
            continue
        seen_urls.add(full)
        listings.append(make_listing(text, full, "Apartment List"))
    print(f"[apartmentlist] found {len(listings)} candidate listings")
    return listings


def scrape_zillow():
    listings = []
    url = "https://www.zillow.com/boulder-co/apartments/"
    print(f"[zillow] fetching {url}")
    status, body = fetch(url)
    if status != 200 or not body:
        print(f"[zillow] skipped (status={status}) -- likely bot-blocked")
        return listings
    soup = BeautifulSoup(body, "html.parser")
    for card in soup.select("article, li"):
        text = card.get_text(" ", strip=True)
        if parse_rent(text) is None:
            continue
        link = card.find("a", href=True)
        if not link:
            continue
        href = link["href"]
        full = href if href.startswith("http") else f"https://www.zillow.com{href}"
        listings.append(make_listing(text, full, "Zillow"))
    print(f"[zillow] found {len(listings)} candidate listings")
    return listings


def scrape_apartments_com():
    listings = []
    url = "https://www.apartments.com/boulder-co/"
    print(f"[apartments.com] fetching {url}")
    status, body = fetch(url)
    if status != 200 or not body:
        print(f"[apartments.com] skipped (status={status}) -- likely bot-blocked")
        return listings
    soup = BeautifulSoup(body, "html.parser")
    for card in soup.select("article.placard, li.mortar-wrapper"):
        text = card.get_text(" ", strip=True)
        if parse_rent(text) is None:
            continue
        link = card.find("a", href=True)
        href = link["href"] if link else url
        listings.append(make_listing(text, href, "Apartments.com"))
    print(f"[apartments.com] found {len(listings)} candidate listings")
    return listings


SCRAPERS = [
    ("Apartment List", scrape_apartmentlist),
    ("Zillow", scrape_zillow),
    ("Apartments.com", scrape_apartments_com),
]


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def passes_filters(listing):
    rent = listing.get("rent")
    if rent is None or rent > MAX_RENT:
        return False
    beds = listing.get("beds")
    if beds is not None and beds > MAX_BEDS:
        return False
    z = listing.get("zip")
    # Only enforce the ZIP guardrail when a ZIP was actually detected, so we
    # never silently drop a good listing that just didn't print its ZIP.
    if z is not None and ALLOWED_ZIPS and z not in ALLOWED_ZIPS:
        return False
    return True


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------
def build_html(all_listings, new_ids, site_status):
    now = datetime.now(timezone.utc).astimezone()
    stamp = now.strftime("%A, %B %d %Y at %I:%M %p %Z")

    in_budget = [x for x in all_listings if passes_filters(x)]
    in_budget.sort(key=lambda x: x["rent"])

    rows = []
    for x in in_budget:
        is_new = x["id"] in new_ids
        is_ideal = x["rent"] <= IDEAL_RENT
        badges = ""
        if is_new:
            badges += '<span class="badge new">NEW</span>'
        if is_ideal:
            badges += '<span class="badge ideal">&#9733; under $1,500</span>'
        beds = x.get("beds")
        beds_label = "Studio" if beds == 0 else (f"{beds} BR" if beds else "&mdash;")
        rows.append(f"""
          <tr class="{'newrow' if is_new else ''}">
            <td class="rent">${x['rent']:,}</td>
            <td class="beds">{beds_label}</td>
            <td>{html.escape(x['title'])} {badges}</td>
            <td>{html.escape(x['source'])}</td>
            <td><a href="{html.escape(x['url'])}" target="_blank" rel="noopener">view&nbsp;&rarr;</a></td>
          </tr>""")

    table = "\n".join(rows) if rows else (
        '<tr><td colspan="5" class="empty">No listings under '
        f'${MAX_RENT:,} found this run. Check back in a couple days.</td></tr>'
    )

    status_bits = []
    for name, ok in site_status.items():
        cls = "ok" if ok else "blocked"
        label = "working" if ok else "blocked / no results"
        status_bits.append(f'<span class="site {cls}">{html.escape(name)}: {label}</span>')
    status_line = " ".join(status_bits)

    new_count = len([x for x in in_budget if x["id"] in new_ids])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boulder Housing Watch</title>
<style>
  :root {{
    --bg: #faf8f4; --ink: #1f2a24; --muted: #6b7770;
    --accent: #2f5d50; --new: #b4541f; --line: #e3ddd2;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 2rem 1rem 4rem; background: var(--bg); color: var(--ink);
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
  .wrap {{ max-width: 860px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 .25rem; letter-spacing: -.01em; }}
  .sub {{ color: var(--muted); margin: 0 0 1.5rem; font-size: .92rem; }}
  .summary {{ background: #fff; border: 1px solid var(--line); border-radius: 12px;
    padding: 1rem 1.25rem; margin-bottom: 1.5rem; }}
  .summary strong {{ color: var(--accent); }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
    border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
  th, td {{ text-align: left; padding: .7rem .9rem; border-bottom: 1px solid var(--line); }}
  th {{ background: #f1ede4; font-size: .78rem; text-transform: uppercase;
    letter-spacing: .04em; color: var(--muted); }}
  tr:last-child td {{ border-bottom: none; }}
  .rent {{ font-weight: 700; white-space: nowrap; color: var(--accent); }}
  .beds {{ white-space: nowrap; color: var(--muted); font-size: .9rem; }}
  .newrow {{ background: #fff8f2; }}
  .badge {{ display: inline-block; font-size: .68rem; font-weight: 700;
    padding: .1rem .45rem; border-radius: 999px; margin-left: .35rem;
    vertical-align: middle; text-transform: uppercase; letter-spacing: .03em; }}
  .badge.new {{ background: var(--new); color: #fff; }}
  .badge.ideal {{ background: #e7f0ec; color: var(--accent); }}
  .empty {{ text-align: center; color: var(--muted); padding: 2rem 1rem; }}
  a {{ color: var(--accent); }}
  .status {{ margin-top: 1.5rem; font-size: .8rem; color: var(--muted); }}
  .site {{ display: inline-block; margin-right: .75rem; }}
  .site.ok::before {{ content: "\\25CF "; color: #3a8a5f; }}
  .site.blocked::before {{ content: "\\25CF "; color: #c0392b; }}
  .foot {{ margin-top: 2rem; font-size: .78rem; color: var(--muted); line-height: 1.6; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Boulder Housing Watch</h1>
    <p class="sub">Studios &amp; 1BRs under ${MAX_RENT:,} &middot; within ~5 mi of the East Boulder office &middot; auto-checked daily</p>

    <div class="summary">
      <strong>{len(in_budget)}</strong> listing(s) in budget this run
      &middot; <strong>{new_count}</strong> new since last check
      <br><span style="font-size:.85rem;color:var(--muted)">Last updated {stamp}</span>
    </div>

    <table>
      <thead>
        <tr><th>Rent</th><th>Beds</th><th>Listing</th><th>Source</th><th></th></tr>
      </thead>
      <tbody>
        {table}
      </tbody>
    </table>

    <div class="status">{status_line}</div>

    <p class="foot">
      Criteria: studio or 1BR, max ${MAX_RENT:,}/mo, anywhere in Boulder within roughly
      5 miles of 2000 Central Ave (ZIPs 80301&ndash;80305 and 80503). Listings marked
      &#9733; are at or under your ${IDEAL_RENT:,} ideal. This page is a personal
      convenience tool &mdash; always confirm details (in-unit W/D, parking, outdoor
      space) directly with the listing. Some sites block automated checks; when that
      happens they show as blocked above and you should check them manually. Facebook
      Marketplace and Craigslist are not covered here &mdash; use their own saved-search alerts.
    </p>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    DOCS.mkdir(exist_ok=True)
    seen = load_seen()

    all_listings = []
    site_status = {}
    for name, fn in SCRAPERS:
        try:
            found = fn()
            site_status[name] = len(found) > 0
            all_listings.extend(found)
        except Exception as e:
            print(f"[{name}] crashed: {e}", file=sys.stderr)
            site_status[name] = False
        time.sleep(2)

    in_budget = [x for x in all_listings if passes_filters(x)]
    current_ids = {x["id"] for x in in_budget}
    new_ids = current_ids - seen

    print(f"\nTotal in-budget: {len(in_budget)} | new this run: {len(new_ids)}")

    page = build_html(all_listings, new_ids, site_status)
    OUTPUT_HTML.write_text(page)
    print(f"Wrote {OUTPUT_HTML}")

    save_seen(seen | current_ids)


if __name__ == "__main__":
    main()
