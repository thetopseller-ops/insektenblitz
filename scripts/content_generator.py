"""Content-Generierung via Claude.

Nimmt News-Treffer, laesst Claude einen vollstaendig umgeschriebenen deutschen
Blogpost schreiben und gibt eine strukturierte dict-Form zurueck, die der
html_assembler ins Template rendert.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from github_api import get_file_sha
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

MODEL = "claude-sonnet-4-6"
MAX_HITS = 5  # Skeleton: Top-Treffer; Plan 01-2 filtert/reduziert sauber vor.
REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_api_key() -> str:
    """ANTHROPIC_API_KEY: zuerst Umgebung, dann lokale .env. Klarer Abbruch wenn fehlt."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "ANTHROPIC_API_KEY":
                return value.strip().strip('"').strip("'")
    sys.exit("ANTHROPIC_API_KEY fehlt — bitte in .env setzen (siehe .env.example).")


def _slugify(title: str, max_len: int = 50) -> str:
    s = title.lower()
    for a, b in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    # Kappen am Wortende: callback_data "approve:{slug}" muss unter Telegrams
    # 64-Byte-Limit bleiben (D-01); kurze Slugs sind auch bessere SEO-URLs.
    if len(s) > max_len:
        s = s[:max_len].rsplit("-", 1)[0]
    return s or "eps-post"


def _unique_slug(base: str) -> str:
    """Stellt sicher, dass blog-{slug}.html auf main noch nicht existiert.

    Haengt bei Kollision die Suffixe -2, -3, ... an, bis ein freier Slug
    gefunden ist. Obergrenze 20 Versuche; danach Datums-Suffix als Notanker
    (verhindert Endlosschleife).
    """
    if get_file_sha(f"blog-{base}.html") is None:
        return base
    for n in range(2, 22):
        candidate = f"{base}-{n}"
        if get_file_sha(f"blog-{candidate}.html") is None:
            return candidate
    # Notanker: YYYYMMDD-Suffix (sollte nie gebraucht werden)
    from datetime import date as _date
    return f"{base}-{_date.today().strftime('%Y%m%d')}"


def _clean(text: str, limit: int = 300) -> str:
    """HTML aus Google-News-Anrissen entfernen + kuerzen (fuer den Prompt)."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


PROMPT = """Du bist SEO-Redakteur fuer insektenblitz.com, einen Drohnen-Bekaempfungsservice \
gegen Eichenprozessionsspinner (EPS), Goldafter und Palmenzuensler.

Heute ist der {today} (aktuelles Jahr: {year}). Schreibe aus heutiger Sicht. Verwende im \
Titel und im Text NUR das aktuelle Jahr {year} oder gar keine Jahreszahl — niemals ein \
vergangenes Jahr, auch wenn die Nachrichten-Anrisse aeltere Jahreszahlen nennen.

Hier sind aktuelle Nachrichten-Anrisse zum Thema EPS:

{sources_block}

Schreibe daraus EINEN deutschen Blogpost (600-900 Woerter) im sachlich-informativen, \
familienorientierten Stil von insektenblitz.com. Ziel: Eltern/Anwohner informieren und \
zur kostenlosen Erstberatung fuehren. Liefere 3-4 inhaltliche Abschnitte (sections) mit je \
einer H2-Ueberschrift; mehrere Absaetze innerhalb eines Abschnitts mit Leerzeile (\\n\\n) trennen. \
'tag' ist ein kurzes Label wie 'EPS-Wissen', 'meta_description' max ~155 Zeichen, 'highlight' \
ein kurzer wichtiger Hinweis-Satz fuer eine hervorgehobene Box.

WICHTIG (Rechtssicherheit): Schreibe alle Inhalte VOLLSTAENDIG in eigenen Worten um. \
Zitiere KEINE Originaltexte. Keine Verleumdung von Firmen oder Personen.

Fuer 'hero_keyword': Waehle GENAU EIN passendes Stichwort aus dieser Liste, das zum \
Thema des Posts passt: eiche, wald, baum, saison, standard, familie, kinder, garten, \
haustiere, hund, katze, tier, kind, schule, spielplatz, kindergarten, kita, mallorca, \
palme, palmenzuensler, buero, gewerbe, betrieb, arbeitsschutz, office, firma, drohne, \
inspektion, umwelt, natur, finca, urlaub. Das Feld steuert nur die Bildauswahl."""

# Erzwingt gueltige JSON-Struktur (Anthropic Structured Outputs) — kein fragiles Text-Parsen.
POST_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tag": {"type": "string"},
        "meta_description": {"type": "string"},
        "intro": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["heading", "body"],
                "additionalProperties": False,
            },
        },
        "highlight": {"type": "string"},
        "hero_keyword": {"type": "string"},
    },
    "required": ["title", "tag", "meta_description", "intro", "sections", "highlight", "hero_keyword"],
    "additionalProperties": False,
}


EVERGREEN_PROMPT = """Du bist SEO-Redakteur fuer insektenblitz.com, einen Drohnen-Bekaempfungsservice \
gegen Eichenprozessionsspinner (EPS), Goldafter und Palmenzuensler.

Heute ist der {today} (aktuelles Jahr: {year}). Schreibe aus heutiger Sicht; verwende nur das \
aktuelle Jahr {year} oder gar keine Jahreszahl.

Es liegen heute keine aktuellen Nachrichten vor. Schreibe einen zeitlosen Ratgeber-Blogpost \
zum Thema: "{topic}".

600-900 Woerter, sachlich-informativer, familienorientierter Stil; Ziel: Eltern/Anwohner \
informieren und zur kostenlosen Erstberatung fuehren. Liefere 3-4 inhaltliche Abschnitte \
(sections) mit je einer H2-Ueberschrift; mehrere Absaetze mit Leerzeile (\\n\\n) trennen. \
'tag' kurzes Label wie 'EPS-Ratgeber', 'meta_description' max ~155 Zeichen, 'highlight' ein \
kurzer wichtiger Hinweis-Satz. Schreibe vollstaendig in eigenen Worten.

Fuer 'hero_keyword': Waehle GENAU EIN passendes Stichwort aus dieser Liste: eiche, wald, \
baum, saison, standard, familie, kinder, garten, haustiere, hund, katze, tier, kind, schule, \
spielplatz, kindergarten, kita, mallorca, palme, palmenzuensler, buero, gewerbe, betrieb, \
arbeitsschutz, office, firma, drohne, inspektion, umwelt, natur, finca, urlaub. \
Das Feld steuert nur die Bildauswahl."""


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(min=5, max=20),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_claude(client: anthropic.Anthropic, **kwargs) -> anthropic.types.Message:
    """Wrappt client.messages.create mit Retry/Backoff (2 Versuche, 5-20s Wartezeit).

    Claude-Calls sind teuer -> nur 2 Versuche. reraise=True: nach Erschoepfung
    der Versuche wird die originale Exception weitergegeben (sys.exit bleibt erhalten).
    msg.usage ist auf dem zurueckgegebenen Message-Objekt weiterhin verfuegbar (04-09).
    """
    return client.messages.create(**kwargs)


def generate_post(hits: list[dict], published_titles: "list | None" = None) -> dict:
    """Treffer -> Post-dict (title, slug, tag, meta_description, intro, sections, highlight, sources).

    `sources` ist eine Liste von {"url", "label"} (label = Medienname/Reddit). Bei Evergreen leer.

    Args:
        hits:             Liste von News-Treffern (oder Evergreen-Hit).
        published_titles: Bereits veroeffentlichte Post-Titel fuer Duplikat-Vermeidung (D-07).
                          Wenn nicht-leer, erhaelt Claude einen Anti-Duplikat-Block im Prompt.
    """
    key = _load_api_key()
    hits = [h for h in hits if h.get("title")][:MAX_HITS]
    if not hits:
        sys.exit("Keine verwertbaren Treffer fuer die Generierung.")

    today_str = date.today().strftime("%d.%m.%Y")
    year = date.today().year
    evergreen = bool(hits[0].get("evergreen"))

    # D-07: Anti-Duplikat-Block fuer Claude (nur wenn Titel vorliegen)
    anti_dup_block = ""
    if published_titles:
        titles_list = "\n".join(f"- {t}" for t in published_titles)
        anti_dup_block = (
            f"\n\nBereits veroeffentlichte Themen (NICHT wiederholen, neuen Blickwinkel waehlen):\n"
            f"{titles_list}"
        )

    if evergreen:
        prompt = EVERGREEN_PROMPT.format(topic=hits[0]["title"], today=today_str, year=year)
        sources = []  # keine echten Quellen -> HTML laesst den Block weg
    else:
        sources_block = "\n".join(f"- {h['title']}: {_clean(h.get('summary', ''))}" for h in hits)
        prompt = PROMPT.format(sources_block=sources_block, today=today_str, year=year)
        sources = [
            {"url": h["url"], "label": h.get("source_label") or h["url"]}
            for h in hits
            if h.get("url")
        ]

    # Anti-Duplikat-Block an den Prompt anhaengen (beide Prompt-Typen)
    if anti_dup_block:
        prompt += anti_dup_block

    client = anthropic.Anthropic(api_key=key)
    msg = _call_claude(
        client,
        model=MODEL,
        max_tokens=3000,
        output_config={"format": {"type": "json_schema", "schema": POST_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    # output_config erzwingt schema-gueltiges JSON -> kein Fence-Stripping/Repair noetig.
    text = next((b.text for b in msg.content if b.type == "text"), None)
    if text is None:
        sys.exit("Claude-Antwort enthielt keinen Text-Block — Generierung abgebrochen.")
    post = json.loads(text)

    # D-11: Kosten-Schaetzung aus msg.usage (Sonnet-4.6: $3/MTok input, $15/MTok output).
    # Defensiv: falls msg.usage fehlt oder unvollstaendig, keinen Crash ausloesen.
    try:
        input_tok = msg.usage.input_tokens
        output_tok = msg.usage.output_tokens
        kosten_usd = (input_tok / 1_000_000 * 3.0) + (output_tok / 1_000_000 * 15.0)
        post["cost_eur"] = round(kosten_usd * 0.93, 3)  # USD->EUR-Faktor 0.93 (statisch)
    except Exception:
        pass  # cost_eur bleibt weg; keine Kosten-Zeile in der Vorschau (kein Crash)

    post["slug"] = _unique_slug(_slugify(post.get("title", "")))
    post["sources"] = sources
    return post


if __name__ == "__main__":
    from news_scraper import fetch_google_news

    result = generate_post(fetch_google_news())
    print("Titel:", result.get("title"))
    print("Slug: ", result.get("slug"))
    print("Sections:", len(result.get("sections", [])))
    print("Quellen:", len(result.get("sources", [])))
