"""Registriert oder loescht den Telegram-Webhook. Einmalig beim Setup + Notfall.

  python scripts/set_webhook.py set https://<deine-site>.netlify.app/telegram-webhook
  python scripts/set_webhook.py delete
  python scripts/set_webhook.py info     # Diagnose: URL + letzter Zustellfehler

set:    registriert die URL + secret_token (aus TELEGRAM_WEBHOOK_SECRET). Danach
        liefert getUpdates 409 — Polling ist abgeloest, Klicks gehen an die URL.
delete: entfernt den Webhook -> Polling (post-approval / Nachhoer-Loop) wieder moeglich.
        Notfall-Wiederherstellung, falls das Relay/Netlify ausfaellt.

Secrets aus Umgebung/.env: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET.
Token erscheint nur in der URL, nie in der Ausgabe.
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from telegram_bot import _load_secret, TELEGRAM_API


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("set", "delete", "info"):
        sys.exit("Aufruf: python scripts/set_webhook.py set <url> | delete | info")

    token = _load_secret("TELEGRAM_BOT_TOKEN")

    if sys.argv[1] == "info":
        # Diagnose: zeigt, was Telegram ueber den Webhook weiss — v.a. die letzte
        # Zustell-Fehlermeldung (z.B. "Wrong response from the webhook: 401").
        resp = requests.post(
            TELEGRAM_API.format(token=token, method="getWebhookInfo"), timeout=15
        )
        info = resp.json().get("result", {})
        print(f"url:                   {info.get('url')}")
        print(f"pending_update_count:  {info.get('pending_update_count')}")
        print(f"last_error_message:    {info.get('last_error_message')}")
        print(f"last_error_date:       {info.get('last_error_date')}")
        print(f"allowed_updates:       {info.get('allowed_updates')}")
        return

    if sys.argv[1] == "set":
        if len(sys.argv) < 3:
            sys.exit("URL fehlt: python scripts/set_webhook.py set <url>")
        url = sys.argv[2]
        secret = _load_secret("TELEGRAM_WEBHOOK_SECRET")
        resp = requests.post(
            TELEGRAM_API.format(token=token, method="setWebhook"),
            json={
                "url": url,
                "secret_token": secret,
                # Nur die Update-Typen, die wir verarbeiten (weniger Rauschen).
                "allowed_updates": ["callback_query", "message"],
            },
            timeout=15,
        )
    else:
        resp = requests.post(
            TELEGRAM_API.format(token=token, method="deleteWebhook"),
            json={"drop_pending_updates": False},  # offene Klicks NICHT verwerfen
            timeout=15,
        )

    try:
        data = resp.json()
    except ValueError:
        # Kein Token ausgeben (steckt in der URL) — nur Statuscode.
        sys.exit(f"Telegram API Fehler: HTTP {resp.status_code} (keine JSON-Antwort)")
    if data.get("ok"):
        print(f"OK: {data.get('description', sys.argv[1])}")
    else:
        sys.exit(f"Telegram API Fehler: HTTP {resp.status_code} — {data.get('description')}")


if __name__ == "__main__":
    main()
