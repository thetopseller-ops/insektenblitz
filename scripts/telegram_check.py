"""Skript B: Prueft ob Malte auf die Telegram-Freigabe geantwortet hat.

State-frei (Plan 03-03): kein lokaler Pending-State noetig. Der Draft liegt im
Repo (Quelle der Wahrheit), der Slug kommt aus der callback_data. getUpdates wird
EINMAL gepollt; jedes verarbeitete Update wird sofort per Offset (update_id+1)
bestaetigt -> keine Doppelverarbeitung zwischen zwei ephemeren Actions-Laeufen.

Approve (D-05/PUB-01):
  Draft-Inhalt lesen + in EINEM atomaren Commit (commit_files):
    - blog-[slug].html hinzufuegen
    - draft-[datum].html entfernen
    - sitemap.xml aktualisieren (D-04)
    - index.html erste Blog-Karte einfuegen (D-05)
  -> genau ein Commit auf main, ein Netlify-Deploy, kein Teil-Zustand.

Reject (D-06/PUB-02):
  draft-[datum].html per API loeschen (Single-File, delete_file).

Sicherheit (T-02-06): Nur callback_query von der eigenen TELEGRAM_CHAT_ID
wird verarbeitet — fremde Klicks werden ignoriert.

Aufruf:  python scripts/telegram_check.py
"""
import html
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ importierbar machen

from telegram_bot import get_updates, answer_callback_query, send_message, _load_secret
from github_api import commit_files, delete_file, get_text_file
from html_assembler import final_filename


# ---------------------------------------------------------------------------
# D-04: Sitemap-Update (defusedxml, XXE-sicher, T-04-14)
# ---------------------------------------------------------------------------

def _update_sitemap(slug: str, site_base_url: str) -> str:
    """Liest sitemap.xml, fuegt neuen Post-Eintrag ein (Duplikat-sicher), gibt XML-String zurueck.

    - Parst sitemap.xml per defusedxml.ElementTree (XXE/Billion-Laughs deaktiviert, T-04-14).
    - Prueft ob loc fuer diesen Slug bereits existiert; falls ja: Originalinhalt unveraendert
      zurueckgeben (kein Doppel-Eintrag).
    - Sonst: neues <url>-Element mit loc/lastmod/changefreq/priority anhaengen.
    - ET.indent() (Python 3.9+, CI nutzt 3.11) formatiert den Baum.
    - Rueckgabe: serialisierter XML-String (utf-8, mit xml_declaration) — direkt als
      commit_files-content verwendbar.
    """
    import defusedxml.ElementTree as dET
    import xml.etree.ElementTree as ET
    from datetime import date
    from io import BytesIO

    SITEMAP = Path(__file__).resolve().parent.parent / "sitemap.xml"
    # defusedxml fuer sicheres Parsen (XXE/Billion-Laughs deaktiviert, T-04-14)
    tree = dET.parse(str(SITEMAP))
    root = tree.getroot()
    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"

    new_url = f"{site_base_url.rstrip('/')}/blog-{slug}.html"
    existing = [e.text for e in root.findall(f".//{{{ns}}}loc")]
    if new_url in existing:
        # Duplikat-Schutz: Sitemap bleibt unveraendert
        return SITEMAP.read_text(encoding="utf-8")

    # Mutation via stdlib ET (SubElement, indent, write) — XXE bereits beim Parse neutralisiert
    url_el = ET.SubElement(root, f"{{{ns}}}url")
    ET.SubElement(url_el, f"{{{ns}}}loc").text = new_url
    ET.SubElement(url_el, f"{{{ns}}}lastmod").text = date.today().isoformat()
    ET.SubElement(url_el, f"{{{ns}}}changefreq").text = "monthly"
    ET.SubElement(url_el, f"{{{ns}}}priority").text = "0.8"

    ET.indent(tree, space="  ")  # Python 3.9+; CI nutzt 3.11
    buf = BytesIO()
    tree.write(buf, xml_declaration=True, encoding="utf-8")
    return buf.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# D-05: Startseiten-Karte (T-04-15: alle dynamischen Felder via html.escape)
# ---------------------------------------------------------------------------

# Eindeutiger Anker im Blog-Grid (index.html Zeile 865, kommt genau einmal vor)
GRID_ANCHOR = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 30px; margin-top: 50px;">'


def _build_blog_card(slug: str, title: str, tag: str, hero_image: str, meta_desc: str, read_min: "str | None" = None) -> str:
    """Erzeugt das Karten-HTML exakt nach dem kanonischen Muster (UI-SPEC 6.2/6.3).

    Alle dynamischen Felder (title, tag, meta_desc, hero_image, slug) werden via
    html.escape eingefuegt (T-04-15: Injection-Schutz).
    """
    import html as html_lib
    from datetime import date
    today = date.today()
    monate_de = [
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    ]
    monat_jahr = f"{monate_de[today.month - 1]} {today.year}"
    # Lesezeit-Suffix wie in Maltes Karten-Schema ("Mai 2025 · 5 Min Lesezeit").
    # read_min kommt beim Approve aus der bestehenden Artikel-Meta-Zeile (gleiche
    # Quelle wie die Artikelseite -> identische Zahl); nur Ziffern, kein Injection-Risiko.
    meta_zeile = monat_jahr if not read_min else f"{monat_jahr} · {read_min} Min Lesezeit"
    return (
        f'\n        <!-- ARTIKEL-START: {html_lib.escape(title[:40])} -->\n'
        f'        <div style="background: white; border-radius: var(--radius); overflow: hidden; '
        f'box-shadow: 0 4px 14px rgba(0,0,0,0.08); transition: all 0.3s; display: flex; flex-direction: column;">\n'
        f'          <div style="position: relative;">\n'
        f'            <img src="{html_lib.escape(hero_image)}" alt="{html_lib.escape(title)}" '
        f'style="width: 100%; height: 200px; object-fit: cover; display: block;" loading="lazy" decoding="async">\n'
        f'            <span style="position: absolute; top: 12px; left: 12px; background: var(--primary-green); '
        f'color: white; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 20px;">'
        f'{html_lib.escape(tag)}</span>\n'
        f'          </div>\n'
        f'          <div style="padding: 22px; flex-grow: 1; display: flex; flex-direction: column;">\n'
        f'            <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">{meta_zeile}</p>\n'
        f'            <h3 style="font-size: 16px; font-weight: 700; color: var(--text-dark); '
        f'margin-bottom: 12px; line-height: 1.4;">{html_lib.escape(title)}</h3>\n'
        f'            <p style="font-size: 14px; color: var(--text-light); line-height: 1.7; '
        f'margin-bottom: 18px; flex-grow: 1;">{html_lib.escape(meta_desc)}</p>\n'
        f'            <a href="blog-{html_lib.escape(slug)}.html" '
        f'style="color: var(--primary-green); font-weight: 700; font-size: 13px;">Artikel lesen &rarr;</a>\n'
        f'          </div>\n'
        f'        </div>\n'
        f'        <!-- ARTIKEL-END -->'
    )


def _build_index_card_in_html(slug: str, title: str, draft_content: str) -> str:
    """Liest index.html von main, fuegt neue Blog-Karte als ERSTE Karte ein.

    Metadaten (tag, hero_image, meta_desc) werden per Regex aus dem Draft-HTML extrahiert
    (UI-SPEC 6.4). Insertion per str.replace(GRID_ANCHOR, GRID_ANCHOR + card, 1) — kein
    Regex auf der HTML-Struktur, nur gezielter String-Replace am eindeutigen Anker (T-04-15).

    Falls der Anker nicht gefunden wird: WARNUNG ausgeben + unveraendertes index_html
    zurueckgeben (kein Crash).
    """
    import re as _re
    import html as html_lib

    index_html = get_text_file("index.html")

    # Metadaten aus Draft-HTML extrahieren (UI-SPEC 6.4)
    tag_m = _re.search(r'<span class="tag">(.*?)</span>', draft_content)
    tag = html_lib.unescape(tag_m.group(1)) if tag_m else "EPS-Wissen"

    hero_m = _re.search(r'<img class="hero-img" src="([^"]+)"', draft_content)
    hero_image = hero_m.group(1) if hero_m else "images/blog-1-eiche.jpg"

    desc_m = _re.search(r'<meta name="description" content="([^"]+)"', draft_content)
    meta_desc = html_lib.unescape(desc_m.group(1)) if desc_m else ""

    # Lesezeit aus der bereits gerenderten Artikel-Meta-Zeile ziehen (html_assembler
    # schreibt "... &middot; N Minuten Lesezeit &middot; ...") -> Karte zeigt dieselbe Zahl.
    read_m = _re.search(r"(\d+)\s*Minuten Lesezeit", draft_content)
    read_min = read_m.group(1) if read_m else None

    card_html = _build_blog_card(slug, title, tag, hero_image, meta_desc, read_min)

    if GRID_ANCHOR not in index_html:
        print("  WARNUNG: Blog-Grid-Anker nicht in index.html gefunden — Karte nicht eingefuegt.")
        return index_html

    # Neueste Karte als erste Karte einfuegen (count=1: nur erster Treffer, T-04-15)
    index_html = index_html.replace(GRID_ANCHOR, GRID_ANCHOR + card_html, 1)

    # Startseite auf hoechstens MAX_TOTAL_CARDS Karten begrenzen. Gezaehlt werden
    # ALLE Karten (Maltes handgemachte + automatische) ueber den Link 'href="blog-'
    # (kommt genau einmal pro Karte vor). Entfernt werden NUR Auto-Karten mit
    # ARTIKEL-START/END-Marker, aelteste zuerst — Maltes Karten und Alt-Format-
    # Karten ohne Marker bleiben immer stehen.
    MAX_TOTAL_CARDS = 9
    grid_start = index_html.find(GRID_ANCHOR)
    blocks = list(_re.finditer(
        r"\n        <!-- ARTIKEL-START:.*?<!-- ARTIKEL-END -->",
        index_html, _re.DOTALL,
    ))
    # blocks in Dokumentreihenfolge = neueste -> aelteste. Aelteste (am Ende) zuerst
    # entfernen, bis die Gesamtzahl <= MAX_TOTAL_CARDS ist. Von hinten loeschen haelt
    # die frueheren Match-Offsets gueltig.
    for m in reversed(blocks):
        if index_html.count('href="blog-', grid_start) <= MAX_TOTAL_CARDS:
            break
        index_html = index_html[:m.start()] + index_html[m.end():]
    return index_html


# ---------------------------------------------------------------------------
# Core approve/reject logic
# ---------------------------------------------------------------------------

def _do_approve(state: dict) -> str:
    """Approve-Pfad (D-05 + D-03 + D-09): Draft -> blog-[slug].html in EINEM atomaren Commit.

    Liest den Draft-Inhalt von main (get_text_file), dann ein einziger
    commit_files-Aufruf der gleichzeitig:
      - blog-[slug].html hinzufuegt (finaler Post)
      - draft-[datum].html entfernt
    Damit gibt es genau einen Commit und einen Netlify-Deploy — kein
    Teil-Zustand-Fenster, wenn ein zweiter Call fehlschlagen wuerde.

    Neu (04-04):
      - Extrahiert echten Titel via <h1>-Regex aus Draft-Inhalt (state["title"] = slug, L-05)
      - D-03-Reset: ersetzt noindex, nofollow durch index, follow im finalen Post-Content
      - Gibt extrahierten Titel zurueck (fuer Live-Link-Bestaetigungs-Nachricht in main())

    Hinweis: commit_files-Liste als erweiterbare Struktur belassen (04-06 fuegt Sitemap + Index ein).

    Returns:
        Echter Titel des Posts (aus <h1>), Fallback = state["slug"].
    """
    slug = state["slug"]
    final = final_filename(slug)
    draft = state["draft_filename"]

    print(f"  Approve: lese Draft '{draft}' von main ...")
    content = get_text_file(draft)

    # Titel aus Draft-HTML extrahieren (state["title"] traegt nur den Slug — L-05)
    m = re.search(r"<h1>(.*?)</h1>", content)
    title = html.unescape(m.group(1)) if m else state["slug"]

    # D-03-Reset: Draft ist noindex,nofollow (04-02); finaler Post muss index,follow sein
    content = content.replace(
        '<meta name="robots" content="noindex, nofollow" />',
        '<meta name="robots" content="index, follow" />',
        1,  # maxreplace=1 — nur den ersten Treffer (genau ein robots-Tag pro Seite)
    )

    # D-04: Sitemap mit neuem Post-Eintrag (Duplikat-sicher, defusedxml, T-04-14)
    site_url = _load_secret("SITE_BASE_URL")
    sitemap_content = _update_sitemap(slug, site_url)

    # D-05: Startseiten-Karte als erste Karte in index.html (T-04-15)
    index_content = _build_index_card_in_html(slug, title, content)

    print(f"  Approve: atomarer Commit ({draft} -> {final} + sitemap + index) ...")
    commit_files(
        [
            # Finalen Post hinzufuegen / aktualisieren (robots bereits index,follow)
            {"path": final, "content": content},
            # Draft entfernen (sha=None im Tree -> Datei geloescht)
            {"path": draft, "delete": True},
            # D-04: Sitemap-Eintrag fuer neuen Post
            {"path": "sitemap.xml", "content": sitemap_content},
            # D-05: Neue Blog-Karte als erste Karte auf der Startseite
            {"path": "index.html", "content": index_content},
        ],
        f"Blogpost veroeffentlicht: {title}",
    )
    print(f"  Approve: '{final}' ist live, Draft entfernt, Sitemap + Startseite aktualisiert.")
    return title


def _do_reject(state: dict) -> None:
    """Reject-Pfad (D-06): Draft loeschen (Single-File, bewusst einfach).

    Kein atomarer Multi-Datei-Bedarf — Reject entfernt nur eine Datei.
    """
    draft = state["draft_filename"]
    print(f"  Reject: loesche Draft '{draft}' ...")
    delete_file(draft, "Draft verworfen")
    print(f"  Reject: Draft entfernt, nichts geht live.")


def _find_draft_in_repo() -> "str | None":
    """Findet den neuesten draft-*.html im Repo via GitHub Contents-API.

    State-frei (Repo = Quelle der Wahrheit): listet das Repo-Root, filtert auf
    draft-*.html und gibt den alphabetisch letzten zurueck (= chronologisch, da
    der Dateiname YYYY-MM-DD traegt). Kein Treffer -> None.
    """
    import requests
    from github_api import _load_secret, _get_headers

    repo = _load_secret("GH_REPO")
    pat = _load_secret("GH_PAT")  # in Actions auf GITHUB_TOKEN gemappt (Plan 03-01)
    url = f"https://api.github.com/repos/{repo}/contents/"
    resp = requests.get(url, headers=_get_headers(pat), timeout=15)
    if not resp.ok:
        return None
    files = [
        f["name"]
        for f in resp.json()
        if f.get("type") == "file"
        and f["name"].startswith("draft-")
        and f["name"].endswith(".html")
    ]
    return sorted(files)[-1] if files else None


def process_update(upd: dict, own_chat_id: str) -> str:
    """Verarbeitet GENAU EIN Update-Dict und gibt den Verarbeitungs-Status zurueck.

    Rueckgabe:
        "handled"  — terminale Verarbeitung: Approve oder Reject wurde ausgefuehrt.
                     Der Aufrufer (main() oder Nachhoer-Loop) soll danach beenden/stoppen.
        "skipped"  — Update ignoriert oder uebersprungen (fremde Chat-ID, unbekannter
                     Callback, kein relevanter Befehl). Offset wird trotzdem bestaetigt.
        "launched" — /neuerpost wurde ausgefuehrt (Subprocess gestartet). main() kehrt
                     danach zurueck; Nachhoer-Loop kann weiterlaufen oder enden.

    Security:
        - Chat-ID-Filter (T-03-07 / T-04.1-01): own_chat_id wird gegen cq["message"]
          ["chat"]["id"] UND cq["from"]["id"] geprueft — fremde IDs werden ignoriert.
        - Kein Token in Logs/Exceptions (T-04.1-02): keine {e}/str(resp)-Ausgaben.

    Single-Delivery (T-04.1-03): der Offset wird nach JEDEM Update per
    get_updates(offset=update_id + 1) bestaetigt — auch bei "skipped". Das
    garantiert, dass dasselbe Update weder vom Nachhoer-Loop noch vom
    post-approval-Cron ein zweites Mal gesehen wird.

    Args:
        upd:         Ein einzelnes Update-Objekt aus get_updates().
        own_chat_id: Die eigene TELEGRAM_CHAT_ID als String (wird gegen das Update
                     geprueft; der Aufrufer laedt sie einmalig und uebergibt sie).
    """
    update_id = upd["update_id"]
    cq = upd.get("callback_query")

    if not cq:
        # Text-Nachrichten: /neuerpost oder unbekannter Befehl
        msg = upd.get("message", {})
        msg_text = (msg.get("text") or "").strip()
        if msg_text.startswith("/neuerpost"):
            # Sicherheits-Filter (T-04-17): nur eigene Chat-ID darf kostenpflichtige
            # Generierung ausloesen — fremde Befehle werden still verworfen.
            msg_chat = str(msg.get("chat", {}).get("id", ""))
            msg_from = str(msg.get("from", {}).get("id", ""))
            if own_chat_id not in (msg_chat, msg_from):
                print("  Fremder /neuerpost — ignoriert (T-04-17).")
                get_updates(offset=update_id + 1)
                return "skipped"
            # Optionales Thema: "/neuerpost Goldafter" -> thema = "Goldafter"
            parts = msg_text.split(None, 1)
            thema = parts[1].strip() if len(parts) > 1 else ""
            # content_machine als Subprocess (T-04-18: kein shell=True -> keine Injection)
            env = {**os.environ, "INPUT_THEMA": thema}
            subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parent / "content_machine.py")],
                env=env,
                check=True,
            )
            send_message(f"Generierungslauf gestartet (Thema: {thema or 'aktuell'})...")
            get_updates(offset=update_id + 1)  # Offset bestaetigen — keine Doppelverarbeitung
            return "launched"
        # Kein bekannter Befehl: bestaetigen und ueberspringen.
        get_updates(offset=update_id + 1)
        return "skipped"

    # callback_query: chat_id unter cq["message"]["chat"]["id"] oder cq["from"]["id"]
    # Beide pruefen, damit der Filter auch bei editierten/geloeschten Nachrichten greift.
    msg_chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    from_id = str(cq.get("from", {}).get("id", ""))
    if own_chat_id not in (msg_chat_id, from_id):
        print(f"  Fremde Chat-ID ({msg_chat_id or from_id}) — ignoriert (T-03-07).")
        get_updates(offset=update_id + 1)  # bestaetigen, nicht erneut holen
        return "skipped"

    data = cq.get("data", "")

    if data.startswith("approve:"):
        slug = data.split(":", 1)[1]
        draft = _find_draft_in_repo()
        if draft is None:
            print("Kein offener Draft im Repo gefunden.")
            get_updates(offset=update_id + 1)
            return "handled"
        title = _do_approve({"draft_filename": draft, "slug": slug, "title": slug})
        answer_callback_query(cq["id"], "Veroeffentlicht")
        # D-09: klickbarer Live-Link (Titel als Link-Text, HTML-escaped; NIE MarkdownV2)
        site_url = _load_secret("SITE_BASE_URL").rstrip("/")
        live_url = f"{site_url}/blog-{slug}.html"
        send_message(
            f'✅ Veroeffentlicht: <a href="{live_url}">{html.escape(title)}</a>',
            parse_mode="HTML",
        )
        get_updates(offset=update_id + 1)  # Q2: sofort bestaetigen = Persistenz
        return "handled"

    elif data.startswith("reject:"):
        slug = data.split(":", 1)[1]
        draft = _find_draft_in_repo()
        if draft:
            _do_reject({"draft_filename": draft})
        answer_callback_query(cq["id"], "Verworfen")
        send_message(f"\U0001f5d1 Verworfen: {slug}")
        get_updates(offset=update_id + 1)  # Q2: sofort bestaetigen = Persistenz
        return "handled"

    else:
        # Anderer/alter Callback — bestaetigen und ueberspringen.
        get_updates(offset=update_id + 1)
        return "skipped"


def main() -> None:
    # State-frei (Q1): kein read_pending mehr — der Draft liegt im Repo, der Slug
    # kommt aus callback_data. Offset-Bestaetigung (Q2) ersetzt den Pending-State.
    updates = get_updates(offset=0)
    if not updates:
        print("Keine Updates.")
        return

    # Akzeptanz-Filter (T-02-06 / T-03-07): nur die eigene Chat-ID.
    # str-Vergleich, da chat_id in Telegram-Objekten int oder str sein kann.
    own_chat_id = str(_load_secret("TELEGRAM_CHAT_ID"))

    for upd in updates:
        result = process_update(upd, own_chat_id)
        if result in ("handled", "launched"):
            return

    print("Kein passendes Update gefunden.")


if __name__ == "__main__":
    main()
