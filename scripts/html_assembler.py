"""HTML-Assembly: Post-dict -> draft-[datum].html im Layout von blog-eps-buerogebaeude.html.

Style, Nav, CTA-Box und Footer werden zur Laufzeit DIREKT aus dem Template
extrahiert -> garantiert 1:1 identische Optik (HTML-01). Schema.org BlogPosting
JSON-LD wird neu in den <head> injiziert (HTML-02).
"""
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_FILE = REPO_ROOT / "blog-eps-buerogebaeude.html"
# Style/Nav/Footer kommen aus TEMPLATE_FILE (Maltes neue Optik, 04-05). Die CTA-Box
# ziehen wir bewusst aus blog-eps-saison.html: dort steht Maltes Standard-CTA mit
# Telefon-Button ("📞 ... anrufen"), die 3 von 4 Posts nutzen. buerogebaeude hat eine
# abweichende "Jetzt Termin vereinbaren"-Variante. Klassen (.cta-box/.btn) sind in
# TEMPLATE_FILE gestylt -> die saison-CTA rendert korrekt mit der neuen Optik.
CTA_SOURCE_FILE = REPO_ROOT / "blog-eps-saison.html"
DOMAIN = "https://insektenblitz.com"

_MONTHS_DE = [
    "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

HERO_MAP = {
    "eiche":         "images/blog-1-eiche.jpg",
    "wald":          "images/blog-1-eiche.jpg",
    "baum":          "images/blog-1-eiche.jpg",
    "saison":        "images/blog-1-eiche.jpg",
    "standard":      "images/blog-1-eiche.jpg",
    "familie":       "images/blog-2-familie.jpg",
    "kinder":        "images/blog-2-familie.jpg",
    "garten":        "images/blog-2-familie.jpg",
    "haustiere":     "images/blog-2-familie.jpg",
    "hund":          "images/alert-haustiere.jpg",
    "katze":         "images/alert-haustiere.jpg",
    "tier":          "images/alert-haustiere.jpg",
    "kind":          "images/alert-kinder.jpg",
    "schule":        "images/alert-kinder.jpg",
    "spielplatz":    "images/alert-kinder.jpg",
    "kindergarten":  "images/hero-kindergarten.jpg",
    "kita":          "images/hero-kindergarten.jpg",
    "mallorca":      "images/blog-3-mallorca.jpg",
    "palme":         "images/blog-3-mallorca.jpg",
    "palmenzuensler": "images/blog-3-mallorca.jpg",
    "buero":         "images/blog-4-buero.jpg",
    "gewerbe":       "images/blog-4-buero.jpg",
    "betrieb":       "images/blog-4-buero.jpg",
    "arbeitsschutz": "images/blog-4-buero.jpg",
    "office":        "images/hero-office.jpg",
    "firma":         "images/hero-office.jpg",
    "drohne":        "images/hero-drohne-wald.jpg",
    "inspektion":    "images/hero-drohne-wald.jpg",
    "umwelt":        "images/alert-umwelt.jpg",
    "natur":         "images/alert-umwelt.jpg",
    "finca":         "images/hero-eps-finka.jpg",
    "urlaub":        "images/hero-eps-finka.jpg",
}
DEFAULT_HERO = "images/blog-1-eiche.jpg"


def resolve_hero(keyword: str) -> str:
    """Mappt POST_SCHEMA-hero_keyword auf vorhandene images/-Assets."""
    return HERO_MAP.get((keyword or "").lower().strip(), DEFAULT_HERO)


def _extract(pattern: str, text: str, what: str) -> str:
    m = re.search(pattern, text, re.S)
    if not m:
        sys.exit(f"Template-Block '{what}' nicht im Quell-HTML gefunden.")
    return m.group(0)


def _reading_time(words: int) -> int:
    return max(3, round(words / 200))


def final_filename(slug: str) -> str:
    """Finaler Dateiname fuer den Publish-Schritt (Draft -> blog-[slug].html)."""
    return f"blog-{slug}.html"


def assemble_draft(post: dict, hero_image: str = "images/blog-1-eiche.jpg") -> str:
    tpl = TEMPLATE_FILE.read_text(encoding="utf-8")
    style = _extract(r"<style>.*?</style>", tpl, "style")
    nav = _extract(r"<nav>.*?</nav>", tpl, "nav")
    footer = _extract(r"<footer>.*?</footer>", tpl, "footer")
    # CTA aus der dedizierten Quelle (Maltes Telefon-Button-Standard), nicht aus tpl.
    cta_src = CTA_SOURCE_FILE.read_text(encoding="utf-8")
    cta = _extract(r'<div class="cta-box">.*?</div>', cta_src, "cta-box")

    title = html.escape(post.get("title", "EPS-Update"))
    tag = html.escape(post.get("tag", "EPS-Wissen"))
    desc = html.escape(post.get("meta_description", ""))
    slug = post.get("slug", "eps-post")
    today = date.today()
    iso = today.isoformat()
    url = f"{DOMAIN}/blog-{slug}.html"
    img_url = f"{DOMAIN}/{hero_image}"

    # --- Body aufbauen ---
    parts = []
    word_count = 0
    intro = (post.get("intro") or "").strip()
    if intro:
        parts.append(f"<p>{html.escape(intro)}</p>")
        word_count += len(intro.split())

    highlight = (post.get("highlight") or "").strip()
    for i, sec in enumerate(post.get("sections", [])):
        heading = (sec.get("heading") or "").strip()
        if heading:
            parts.append(f"<h2>{html.escape(heading)}</h2>")
        for para in re.split(r"\n\n+", (sec.get("body") or "").strip()):
            para = para.strip()
            if para:
                parts.append(f"<p>{html.escape(para)}</p>")
                word_count += len(para.split())
        if i == 0 and highlight:  # Highlight-Box nach dem ersten Abschnitt (wie Template)
            parts.append(f'<div class="highlight"><strong>Wichtig:</strong> {html.escape(highlight)}</div>')

    # Quellen-Block nur wenn echte Quellen vorhanden (Evergreen -> kein Block, Plan 01-2)
    sources = [s for s in post.get("sources", []) if isinstance(s, dict) and s.get("url")]
    if sources:
        links = "".join(
            f'<li><a href="{html.escape(s["url"])}" rel="nofollow" target="_blank">{html.escape(s.get("label") or s["url"])}</a></li>'
            for s in sources
        )
        parts.append(f"<h2>Quellen</h2>\n    <ul>{links}</ul>")

    body_html = "\n    ".join(parts)
    meta_line = f"{_MONTHS_DE[today.month - 1]} {today.year} &middot; {_reading_time(word_count)} Minuten Lesezeit &middot; Insektenblitz"

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.get("title", ""),
        "datePublished": iso,
        "author": {"@type": "Organization", "name": "Insektenblitz"},
        "publisher": {"@type": "Organization", "name": "Insektenblitz"},
        "description": post.get("meta_description", ""),
        "url": url,
        "image": img_url,
    }
    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

    out_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} – Insektenblitz</title>
  <meta name="description" content="{desc}" />
  <meta name="robots" content="noindex, nofollow" />
  <link rel="icon" href="images/logo-insektenblitz.svg" type="image/svg+xml" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:url" content="{url}" />
  <link rel="stylesheet" href="fonts/fonts.css" />
  {style}
  <script type="application/ld+json">
{schema_json}
  </script>
</head>
<body>
  {nav}

  <img class="hero-img" src="{html.escape(hero_image)}" alt="{title}">

  <div class="article-wrap">
    <span class="tag">{tag}</span>
    <h1>{title}</h1>
    <p class="meta">{meta_line}</p>

    {body_html}

    {cta}
  </div>

  {footer}
</body>
</html>
"""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    out_path = REPO_ROOT / f"draft-{ts}.html"
    out_path.write_text(out_html, encoding="utf-8")
    return str(out_path)
