"""Generate feed.json (JSON Feed 1.1) and feed.xml (RSS 2.0) from the
manifest, newest cartridges first. Run after adding a game:

    python tools/make_feed.py
"""
import email.utils
import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = "https://alexkorol.github.io/pyxel-arcade/"


def main():
    with open(os.path.join(ROOT, "demos", "manifest.json"), encoding="utf-8") as f:
        games = json.load(f)["games"]
    games.sort(key=lambda g: g["added"], reverse=True)

    items = []
    rss_items = []
    for g in games:
        url = f"{SITE}games/{g['slug']}.html"
        items.append({
            "id": url,
            "url": url,
            "title": g["title"],
            "content_text": g["description"],
            "image": f"{SITE}demos/{g['slug']}.png",
            "date_published": g["added"] + "T00:00:00Z",
            "tags": g["tags"],
        })
        dt = datetime.strptime(g["added"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        rss_items.append(
            "<item>"
            f"<title>{html.escape(g['title'])}</title>"
            f"<link>{url}</link>"
            f"<guid>{url}</guid>"
            f"<description>{html.escape(g['description'])}</description>"
            f"<pubDate>{email.utils.format_datetime(dt)}</pubDate>"
            "</item>"
        )

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Pyxel Arcade — new cartridges",
        "home_page_url": SITE,
        "feed_url": SITE + "feed.json",
        "description": "Tiny games & toys in pure Python, playable in your browser.",
        "items": items,
    }
    with open(os.path.join(ROOT, "feed.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(feed, f, indent=2)
        f.write("\n")

    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        "<title>Pyxel Arcade — new cartridges</title>"
        f"<link>{SITE}</link>"
        "<description>Tiny games &amp; toys in pure Python, playable in your browser.</description>"
        + "".join(rss_items) +
        "</channel></rss>"
    )
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(rss + "\n")

    print(f"wrote feed.json + feed.xml ({len(items)} items)")


if __name__ == "__main__":
    main()
