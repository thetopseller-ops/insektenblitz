"""Orchestrator der Content-Maschine — Skript A.

Phase 2: collect_hits -> generate -> assemble_draft -> Draft via GitHub-API auf main pushen
-> Telegram-Vorschau mit Approve/Reject-Buttons senden -> Pending-State schreiben.

Die Antwort-Auswertung (Approve/Reject) folgt in Plan 02 (telegram_check.py — Skript B).
Aufruf:  python scripts/content_machine.py
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ importierbar machen

import requests

from news_scraper import collect_hits, forced_evergreen_hit
from content_generator import generate_post
from html_assembler import assemble_draft, resolve_hero
from github_api import push_file, _load_secret, _get_headers
from telegram_bot import send_draft_message, send_post_text, send_message
from pending_state import write_pending


def _published_titles() -> list:
    """D-07: Liest die Titel bereits veroeffentlichter blog-*.html aus dem Repo.

    Listet das Repo-Root via GitHub Contents-API (analog zu _find_draft_in_repo in
    telegram_check.py), filtert auf blog-*.html und leitet einen lesbaren Titel aus
    dem Dateinamen-Slug ab (kein zusaetzlicher API-Call pro Datei — reicht als
    Anti-Duplikat-Signal fuer Claude). Auf die letzten 20 Posts begrenzt.

    Bei Netzfehler oder API-Fehler: tolerant, gibt leere Liste zurueck — die
    Generierung darf nicht am Gedaechtnis-Lookup scheitern (T-04-23).

    Returns:
        Liste lesbarer Titel-Strings (aus den Dateinamen abgeleitet).
    """
    try:
        repo = _load_secret("GH_REPO")
        pat = _load_secret("GH_PAT")
        url = f"https://api.github.com/repos/{repo}/contents/"
        resp = requests.get(url, headers=_get_headers(pat), timeout=15)
        if not resp.ok:
            print(f"  _published_titles: Contents-API {resp.status_code} — leere Titelliste.")
            return []
        files = [
            f["name"]
            for f in resp.json()
            if f.get("type") == "file" and f["name"].startswith("blog-") and f["name"].endswith(".html")
        ]
        # Alphabetisch absteigend (chronologisch, neueste zuerst); letzten 20 Posts
        files.sort(reverse=True)
        files = files[:20]
        # Slug -> lesbarer Titel: "blog-eps-bekampfung-2026.html" -> "eps bekampfung 2026"
        titles = []
        for fname in files:
            slug = fname[len("blog-"):-len(".html")]
            title = slug.replace("-", " ")
            titles.append(title)
        return titles
    except Exception as exc:
        print(f"  _published_titles: Fehler beim Repo-Listing ({type(exc).__name__}) — leere Titelliste.")
        return []


def main() -> None:
    # Demo-Themensteuerung: workflow_dispatch-Input 'thema' (via env INPUT_THEMA)
    # erzwingt ein Evergreen-Thema; leer = normaler aktueller News-Lauf.
    thema = os.environ.get("INPUT_THEMA", "").strip()
    if thema:
        hits = forced_evergreen_hit(thema)
        print("Erzwungenes Thema:", thema)
    else:
        hits = collect_hits()
    if hits and hits[0].get("evergreen"):
        print("Keine aktuellen Treffer — Evergreen-Thema:", hits[0]["title"])
    else:
        print(f"{len(hits)} Treffer (Google News + Reddit, 24-48h) — generiere Post mit Claude ...")

    try:
        # D-07: Themen-Gedaechtnis — publizierte Titel aus dem Repo lesen
        pub_titles = _published_titles()
        if pub_titles:
            print(f"  Themen-Gedaechtnis: {len(pub_titles)} bereits veroeffentlichte Posts geladen.")

        post = generate_post(hits, published_titles=pub_titles)
        print(f"  Titel: {post.get('title')}")

        # Pre-flight: callback_data "approve:{slug}" und "reject:{slug}" muessen
        # <= 64 Byte (UTF-8) bleiben — sonst lehnt Telegram den Button still ab.
        # _slugify kappt auf 50 Z. (= 58 Byte mit "approve:"); der Check faengt
        # Randfaelle ab, in denen ein Kollisions-Suffix die Grenze ueberschreitet.
        slug = post["slug"]
        for prefix in ("approve:", "reject:"):
            if len((prefix + slug).encode("utf-8")) > 64:
                sys.exit(
                    f"Slug zu lang fuer Telegram callback_data (>64 Byte): {slug}"
                )

        hero_image = resolve_hero(post.get("hero_keyword", ""))
        draft_path = assemble_draft(post, hero_image=hero_image)
        name = Path(draft_path).name  # "draft-YYYY-MM-DD.html"

        # Schritt 1: Draft via GitHub Contents-API auf main pushen (Single-File-Push)
        # Netlify deployt automatisch -> Draft ist als {SITE_BASE_URL}/{name} erreichbar
        print(f"\nPushe Draft auf main: {name} ...")
        push_file(name, Path(draft_path).read_bytes(), f"Draft-Vorschau: {post['title']}")

        # Schritt 2a: Volltext zum Korrekturlesen senden (reiner Text, ggf. gesplittet)
        print("Sende Volltext zum Korrekturlesen ...")
        send_post_text(post)

        # Schritt 2b: Telegram-Vorschau mit Approve/Reject-Buttons senden
        print("Sende Telegram-Vorschau ...")
        send_draft_message(
            name, post["slug"], post["title"], post.get("meta_description", ""),
            cost_eur=post.get("cost_eur"),  # D-11: Kosten-Zeile in der Vorschau
        )

        # Schritt 3: Pending-State fuer Skript B (telegram_check.py) speichern
        # message_id und offset entfernt (D-14): telegram_check.py ist state-frei
        # und liest read_pending nie — die Felder waren tot (CONCERNS).
        write_pending({
            "draft_filename": name,
            "slug": post["slug"],
            "title": post["title"],
        })

        print("\nDraft gepusht + Telegram gesendet.")
        print(f"  Titel:    {post['title']}")
        print(f"  Draft:    {name}")
        print("  Pending:  .telegram-pending.json")
        print("\nNaechster Schritt: python scripts/telegram_check.py (Plan 02) ausfuehren,")
        print("um die Antwort auszuwerten (Approve -> live / Reject -> loeschen).")

        # D-12: Health-Ping — nur beim daily-content-Lauf (content_machine.main())
        # post-approval-Lauf ruft telegram_check.py auf, NICHT main() — bleibt ping-frei.
        n_hits = len(hits) if not (hits and hits[0].get("evergreen")) else 0
        send_message(f"Lauf OK — {n_hits} Treffer, Post: {post['title'][:60]}")

    except Exception as exc:
        try:
            msg = f"FEHLER im Generierungslauf: {type(exc).__name__}: {str(exc)[:200]}"
            # Sicherheit (Defense-in-Depth): niemals ein Secret in der Fehlernachricht
            # durchlassen — Telegram-Token-URL, Bot-Token, API-Key oder PAT schwaerzen,
            # falls eine Roh-Exception sie je in str(exc) truege.
            msg = re.sub(r"/bot\d+:[A-Za-z0-9_-]+/", "/bot<redacted>/", msg)
            msg = re.sub(r"\d{6,12}:[A-Za-z0-9_-]{30,}", "<redacted-token>", msg)
            msg = re.sub(r"(sk-ant-|ghp_|github_pat_)[A-Za-z0-9_-]+", r"\1<redacted>", msg)
            send_message(msg)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
