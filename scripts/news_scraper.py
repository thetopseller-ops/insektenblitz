"""News-Scraper fuer EPS-Themen.

Quellen: Google News RSS + Reddit JSON (r/de, r/germany). Kein API-Key.
`collect_hits()` aggregiert beide, filtert auf 24-48h + Relevanz, reduziert auf
3-5 Treffer und faellt bei Flaute auf ein Evergreen-Thema zurueck.
"""
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
from defusedxml.ElementTree import fromstring  # haertet gegen XXE/Entity-Bomben (Threat T-01)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

UA = "insektenblitz-content-bot/0.1 (+https://insektenblitz.com)"
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={q}&hl=de&gl=DE&ceid=DE:de"
REDDIT_SEARCH = "https://www.reddit.com/r/{sub}/search.json?q={q}&sort=new&limit={limit}&restrict_sr=on"

# Relevanz-Begriffe (Sicherheitsnetz gegen tangentiale Reddit-Treffer).
EPS_TERMS = ("eichenprozessionsspinner", "prozessionsspinner", "eps", "raupe", "brennhaare", "gespinst")

# Fallback, wenn keine aktuellen News vorliegen.
EVERGREEN_TOPICS = [
    "Eichenprozessionsspinner und Hunde: So schuetzen Sie Ihr Haustier im Garten",
    "EPS auf Spielplaetzen: Was Eltern jetzt wissen muessen",
    "Was kostet die professionelle Eichenprozessionsspinner-Bekaempfung?",
    "Eichenprozessionsspinner-Nest entdeckt: Die richtigen ersten Schritte",
]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=8),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError)),
    reraise=True,
)
def _fetch_url(url: str, timeout: int = 15) -> requests.Response:
    """GET-Request mit Retry/Backoff bei Timeout/ConnectionError (3 Versuche, 2-8s Wartezeit).

    reraise=True: nach Auswahl der Versuche wird die originale Exception weitergegeben.
    Der Evergreen-Fallback in collect_hits faengt sie auf.
    """
    resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    return resp


def _publisher_from_title(title: str) -> str:
    """Google-News-Titel enden meist mit ' - Medienname' -> als Label nutzen."""
    if " - " in title:
        return title.rsplit(" - ", 1)[1].strip()
    return "Google News"


def fetch_google_news(query: str = "Eichenprozessionsspinner") -> list[dict]:
    """Holt EPS-Artikel aus Google News RSS. Liste von {title,url,summary,published,source_label}."""
    url = GOOGLE_NEWS_RSS.format(q=urllib.parse.quote(query))
    resp = _fetch_url(url)
    root = fromstring(resp.content)  # wirft bei kaputtem XML — bewusst nicht still

    hits = []
    for item in root.iterfind(".//item"):
        title = (item.findtext("title") or "").strip()
        hits.append(
            {
                "title": title,
                "url": (item.findtext("link") or "").strip(),
                "summary": (item.findtext("description") or "").strip(),
                "published": (item.findtext("pubDate") or "").strip(),
                "source_label": _publisher_from_title(title),
            }
        )
    return hits


def fetch_reddit(subreddits=("de", "germany"), query: str = "Eichenprozessionsspinner", limit: int = 5) -> list[dict]:
    """Holt oeffentliche Reddit-Posts via JSON. Eine ausgefallene Quelle killt den Lauf nicht.

    HINWEIS: Reddit blockt unauthentifizierten .json-Zugriff inzwischen mit 403 (Stand 2026-06),
    unabhaengig vom User-Agent. Fuer echten Reddit-Zugriff ist OAuth noetig (Reddit-App
    registrieren -> client_id/secret). Bis dahin faellt diese Quelle sauber aus; Google News
    traegt Phase 1. Reddit-OAuth ist als Phase-2-Aufgabe vorgesehen.
    """
    hits = []
    for sub in subreddits:
        url = REDDIT_SEARCH.format(sub=sub, q=urllib.parse.quote(query), limit=limit)
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=15)  # UA zwingend, sonst 429
            resp.raise_for_status()
            children = resp.json().get("data", {}).get("children", [])
        except Exception as e:  # noqa: BLE001 — Quelle darf ausfallen, nicht den Lauf abbrechen
            print(f"  Reddit r/{sub} fehlgeschlagen: {e}")
            continue
        for child in children:
            d = child.get("data", {})
            created = d.get("created_utc")
            published = ""
            if created:
                # als RFC822, damit _parse_when (parsedate_to_datetime) einheitlich greift
                published = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
            hits.append(
                {
                    "title": (d.get("title") or "").strip(),
                    "url": d.get("url") or ("https://www.reddit.com" + d.get("permalink", "")),
                    "summary": (d.get("selftext") or "")[:300],
                    "published": published,
                    "source_label": f"Reddit r/{sub}",
                }
            )
    return hits


def _parse_when(hit: dict):
    """published (RFC822) -> aware datetime, oder None wenn nicht parsebar."""
    raw = hit.get("published")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _relevant(hit: dict) -> bool:
    text = (hit.get("title", "") + " " + hit.get("summary", "")).lower()
    return any(term in text for term in EPS_TERMS)


def collect_hits(max_hits: int = 5, hours: int = 48) -> list[dict]:
    """Aggregiert beide Quellen, filtert auf 24-48h + Relevanz, reduziert auf 3-5.

    Bei 0 Treffern: genau EIN Evergreen-Eintrag (markiert mit evergreen=True).
    """
    raw = []
    try:
        raw += fetch_google_news()
    except Exception as e:  # noqa: BLE001 — Quelle darf ausfallen
        print(f"  Google News fehlgeschlagen: {e}")
    raw += fetch_reddit()

    # Dedupe nach normalisiertem Titel.
    seen, deduped = set(), []
    for h in raw:
        key = h.get("title", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(h)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    kept = []
    for h in deduped:
        if not _relevant(h):
            continue
        when = _parse_when(h)
        # Strategie: undatierte Treffer behalten (lieber drin als faelschlich raus).
        if when is not None and when < cutoff:
            continue
        h["_when"] = when
        kept.append(h)

    # Neueste zuerst; undatierte ans Ende.
    kept.sort(key=lambda h: h["_when"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    if kept:
        return kept[:max_hits]

    topic = EVERGREEN_TOPICS[date.today().toordinal() % len(EVERGREEN_TOPICS)]
    return [{"title": topic, "url": "", "summary": "", "published": "", "source_label": "", "evergreen": True}]


def forced_evergreen_hit(topic: str) -> list[dict]:
    """Erzwingt ein Evergreen-Hit-Dict mit gegebenem Titel (Demo-Themensteuerung).

    Liefert exakt das Schema des Evergreen-Branches aus collect_hits, aber mit dem
    uebergebenen topic statt dem datums-rotierten EVERGREEN_TOPICS-Eintrag. So sind
    die 3 Nachweis-Posts sichtbar verschieden (workflow_dispatch-Input 'thema').

    Args:
        topic: Der erzwungene Post-Titel (nicht-leerer String).

    Returns:
        Liste mit genau einem Hit-Dict (evergreen=True), generate_post-kompatibel.
    """
    return [{"title": topic, "url": "", "summary": "", "published": "", "source_label": "", "evergreen": True}]


if __name__ == "__main__":
    found = collect_hits()
    if found and found[0].get("evergreen"):
        print("Keine aktuellen Treffer — Evergreen-Thema:", found[0]["title"])
    else:
        print(f"{len(found)} Treffer (gefiltert, 24-48h):")
        for h in found:
            print(f"  - [{h.get('source_label')}] {h['title']}")
    if not found:
        sys.exit("Unerwartet leer.")
