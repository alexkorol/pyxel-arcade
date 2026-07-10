"""Generate static share pages (games/<slug>.html) with OpenGraph/Twitter
meta from demos/manifest.json. Crawlers get a real page with a preview image;
humans get redirected to the SPA route (#/game/<slug>).

Run after editing the manifest: python tools/make_og_pages.py
"""
import html
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SITE = "https://alexkorol.github.io/pyxel-arcade/"

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{title} — Pyxel Arcade</title>
    <meta name="description" content="{desc}">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="Pyxel Arcade">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{desc}">
    <meta property="og:image" content="{site}demos/{slug}.png">
    <meta property="og:url" content="{site}games/{slug}.html">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{desc}">
    <meta name="twitter:image" content="{site}demos/{slug}.png">
    <link rel="canonical" href="{site}#/game/{slug}">
    <meta http-equiv="refresh" content="0; url={site}#/game/{slug}">
</head>
<body>
    <p>Loading <a href="{site}#/game/{slug}">{title}</a>&hellip;</p>
    <script>location.replace("{site}#/game/{slug}");</script>
</body>
</html>
"""


def main():
    with open(os.path.join(ROOT, "demos", "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)

    out_dir = os.path.join(ROOT, "games")
    os.makedirs(out_dir, exist_ok=True)

    for game in manifest["games"]:
        page = TEMPLATE.format(
            title=html.escape(game["title"], quote=True),
            desc=html.escape(game["description"], quote=True),
            slug=game["slug"],
            site=SITE,
        )
        path = os.path.join(out_dir, game["slug"] + ".html")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()
