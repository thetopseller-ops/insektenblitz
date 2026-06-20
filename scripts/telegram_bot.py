"""Telegram-API Hilfsfunktionen fuer die Content-Maschine.

Stellt Funktionen bereit:
  - send_draft_message  : Vorschau-Nachricht mit Approve/Reject-Buttons senden
  - get_updates         : getUpdates einmal pollen (fuer Skript B / Plan 02)
  - answer_callback_query : Lade-Symbol nach Button-Klick entfernen (Plan 02)

Secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) werden aus der Umgebung / .env geladen.
Bot-Token erscheint nur in der URL, nie in print-Ausgaben oder Fehlermeldungen.
"""
import html
import os
import sys
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

REPO_ROOT = Path(__file__).resolve().parent.parent
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _load_secret(key_name: str) -> str:
    """Laedt einen Secret-Wert: erst os.environ, dann .env-Datei, sonst sys.exit."""
    val = os.environ.get(key_name)
    if val:
        return val
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == key_name:
                return value.strip().strip('"').strip("'")
    sys.exit(f"{key_name} fehlt — bitte in .env setzen (siehe .env.example).")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=8),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _post_telegram(url: str, payload: dict, timeout: int = 15) -> requests.Response:
    """POST-Request an Telegram-API mit Retry/Backoff (3 Versuche, 2-8s Wartezeit).

    Nur fuer den kritischen send_draft_message-Call verwendet (sys.exit bei Fehler).
    reraise=True: nach Erschoepfung der Versuche wirft die originale RequestException.
    Token erscheint nur in der URL (nicht in Logs/Ausgaben) — kein Leak durch reraise.
    """
    return requests.post(url, json=payload, timeout=timeout)


def send_draft_message(
    draft_filename: str,
    slug: str,
    title: str,
    meta_desc: str = "",
    cost_eur: "float | None" = None,
) -> dict:
    """Schickt Approve/Reject-Vorschau-Nachricht an TELEGRAM_CHAT_ID.

    Nachricht enthaelt Titel, Vorschau-Link und zwei Inline-Buttons.
    callback_data traegt Aktion + Slug: "approve:{slug}" / "reject:{slug}".

    Args:
        draft_filename: Dateiname des Drafts (z.B. "draft-2026-06-18.html").
        slug:           URL-Slug des Posts (z.B. "eps-bekampfung-2026").
        title:          Titel des Posts.
        meta_desc:      Optionale Kurzbeschreibung fuer den Nachrichtentext.
        cost_eur:       Optionale Kosten-Schaetzung in Euro (D-11). Fehlt -> keine Kosten-Zeile.

    Returns:
        result-dict aus der Telegram-API-Antwort (enthaelt u.a. message_id).

    Raises:
        SystemExit bei HTTP-Fehler oder Telegram-API-Fehler (kritisch).
    """
    token = _load_secret("TELEGRAM_BOT_TOKEN")
    chat_id = _load_secret("TELEGRAM_CHAT_ID")

    base = os.environ.get("SITE_BASE_URL", "https://insektenblitz.com").rstrip("/")
    preview_url = f"{base}/{draft_filename}"

    # Claude-Ausgabe escapen: parse_mode=HTML wuerde sonst bei &, <, > im Titel
    # oder Meta-Text mit 400 'can't parse entities' brechen (CR-01). Der Draft ist
    # zu dem Zeitpunkt schon gepusht -> Abbruch hier hinterliesse einen verwaisten Draft.
    lines = [
        f"<b>{html.escape(title)}</b>",
        "",
        f"Vorschau: {preview_url}",
    ]
    if meta_desc:
        lines += ["", html.escape(meta_desc)]
    # D-11: Kosten-Zeile nur wenn cost_eur vorhanden (kein Crash bei fehlendem Wert)
    if cost_eur is not None:
        lines += ["", f"Generierung: ~{cost_eur:.2f} €"]

    text = "\n".join(lines)

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Freigeben", "callback_data": f"approve:{slug}"},
                {"text": "Verwerfen", "callback_data": f"reject:{slug}"},
            ]
        ]
    }

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
    }

    try:
        resp = _post_telegram(url, payload, timeout=15)
    except requests.RequestException:
        # Nach 3 Retries mit reraise: Exception-Meldung darf nie die Token-URL enthalten.
        # requests.RequestException-Meldungen tragen den URL-String — daher nur Typ loggen.
        sys.exit("Telegram API Fehler: Netzwerkfehler nach 3 Versuchen (kein Token in Ausgabe).")
    # Kein raise_for_status() hier: das wuerde die nackte HTTPError MIT der
    # Token-URL werfen (Secret-Leak) und Telegrams Klartext-Grund verschlucken.
    # Stattdessen den JSON-Body lesen und "description" ausgeben — ohne Token/URL.
    try:
        data = resp.json()
    except ValueError:
        sys.exit(f"Telegram API Fehler: HTTP {resp.status_code} (keine JSON-Antwort)")
    if not data.get("ok"):
        sys.exit(f"Telegram API Fehler: HTTP {resp.status_code} — {data.get('description')}")
    return data["result"]


def send_message(text: str, parse_mode: str = "") -> None:
    """Sendet eine einfache Text-Nachricht an TELEGRAM_CHAT_ID (Status-Feedback).

    Tolerant: ein fehlgeschlagenes Feedback darf den bereits erfolgten
    Approve/Reject nicht nachtraeglich abbrechen. Robuster als
    answerCallbackQuery, weil es nicht ablaeuft. Kein Token im Log.

    Args:
        text:       Nachrichtentext (ggf. HTML-formatiert wenn parse_mode="HTML").
        parse_mode: Optionaler Telegram-Parse-Modus (z.B. "HTML"). Leer = kein Modus.
    """
    token = _load_secret("TELEGRAM_BOT_TOKEN")
    chat_id = _load_secret("TELEGRAM_CHAT_ID")
    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, json=payload, timeout=10)
    except requests.RequestException:
        print("  send_message fehlgeschlagen (Netzwerkfehler) - kosmetisch, ignoriert.")
        return
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not data.get("ok"):
        print(f"  send_message: HTTP {resp.status_code} - {data.get('description')} (kosmetisch, ignoriert).")


def _split_text(text: str, limit: int = 4000) -> list:
    """Teilt langen Text an Absatzgrenzen in Chunks <= limit (Telegram-Limit 4096)."""
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        # Ein einzelner Absatz > limit wird hart in limit-Stuecke geschnitten,
        # damit nichts still verloren geht (WR-05).
        while len(para) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(para[:limit])
            para = para[limit:]
        if cur and len(cur) + len(para) + 2 > limit:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return chunks


def send_post_text(post: dict) -> None:
    """Sendet den redaktionellen Volltext an TELEGRAM_CHAT_ID (Korrekturlesen).

    Reiner Text (kein parse_mode/HTML -> keine Parse-Fehler): Titel + Intro +
    Abschnitte (Ueberschrift + Body) + Highlight. Bei >4096 Zeichen auf mehrere
    Nachrichten gesplittet. Tolerant via send_message (kein Token-Leak).
    """
    lines = [post.get("title", ""), ""]
    intro = (post.get("intro") or "").strip()
    if intro:
        lines += [intro, ""]
    highlight = (post.get("highlight") or "").strip()
    for i, sec in enumerate(post.get("sections", [])):
        heading = (sec.get("heading") or "").strip()
        if heading:
            lines += [f"=== {heading} ===", ""]
        body = (sec.get("body") or "").strip()
        if body:
            lines += [body, ""]
        if i == 0 and highlight:
            lines += [f"WICHTIG: {highlight}", ""]
    text = "\n".join(lines).strip()
    for chunk in _split_text(text):
        send_message(chunk)


def get_updates(offset: int = 0, long_poll: int = 0) -> list:
    """Pollt getUpdates einmal und gibt Liste von Update-Objekten zurueck.

    Wird von Skript B (telegram_check.py, Plan 02) verwendet.
    Bei Fehler: tolerant (print + leere Liste) — kein Update ist ok,
    naechster Cron-Run holt nach.

    Args:
        offset:    Update-ID-Offset (verhindert Doppelverarbeitung).
        long_poll: Telegram "timeout"-Parameter in Sekunden. Default 0 = Short-Poll
                   (Telegram-timeout=1, requests-Timeout=15 — Rueckwaertskompatibilitaet).
                   Fuer Long-Poll z.B. 25-30 setzen; requests-Timeout wird automatisch
                   auf long_poll + 10 gesetzt, damit Telegram vor requests antwortet.
                   INVARIANT: requests-Timeout > long_poll (sonst bricht requests die
                   Verbindung ab, bevor Telegram antwortet, und der Phase-04.1-Effekt
                   "Sekunden statt Minuten" entfaellt).

    Returns:
        Liste von Update-Dicts (kann leer sein).
    """
    token = _load_secret("TELEGRAM_BOT_TOKEN")
    url = TELEGRAM_API.format(token=token, method="getUpdates")
    if long_poll > 0:
        tg_timeout = long_poll
        req_timeout = long_poll + 10  # INVARIANT: req_timeout > long_poll
    else:
        tg_timeout = 1   # Short-Poll (Default, Rueckwaertskompatibilitaet)
        req_timeout = 15
    try:
        resp = requests.get(url, params={"offset": offset, "timeout": tg_timeout}, timeout=req_timeout)
    except requests.RequestException:
        # Nie {e} ausgeben — die Exception-Meldung enthaelt die Token-URL (Leak).
        print("  getUpdates fehlgeschlagen (Netzwerkfehler) — ignoriert.")
        return []
    try:
        data = resp.json()
    except ValueError:
        print(f"  getUpdates: HTTP {resp.status_code} (keine JSON-Antwort).")
        return []
    if not data.get("ok"):
        print(f"  getUpdates: HTTP {resp.status_code} — {data.get('description')}")
        return []
    return data.get("result", [])


def answer_callback_query(callback_query_id: str, text: str = "") -> None:
    """Beantwortet einen Callback-Query (entfernt das Lade-Symbol nach Button-Klick).

    Wird von Skript B (Plan 02) nach Approve/Reject aufgerufen.
    Bei Fehler: tolerant (nur print) — Lade-Symbol ist kosmetisch.

    Args:
        callback_query_id: ID aus dem callback_query-Objekt.
        text:              Optionaler kurzer Bestaetigungs-Text.
    """
    token = _load_secret("TELEGRAM_BOT_TOKEN")
    url = TELEGRAM_API.format(token=token, method="answerCallbackQuery")
    try:
        resp = requests.post(
            url,
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=10,
        )
    except requests.RequestException:
        # Nie {e} ausgeben — die Exception-Meldung enthaelt die Token-URL (Leak).
        print("  answerCallbackQuery fehlgeschlagen (Netzwerkfehler) — kosmetisch, ignoriert.")
        return
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if not data.get("ok"):
        # 400 "query is too old" ist im Polling-Betrieb normal (kosmetisch).
        print(f"  answerCallbackQuery: HTTP {resp.status_code} — {data.get('description')} (kosmetisch, ignoriert).")
