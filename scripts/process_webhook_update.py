"""Webhook-Einstieg: verarbeitet EIN per repository_dispatch durchgereichtes Telegram-Update.

Wird von .github/workflows/telegram-webhook.yml aufgerufen. Das Relay
(netlify/functions/telegram-webhook.mts) reicht das Telegram-Update an GitHub
Actions; dieser Workflow legt es als Env-Var WEBHOOK_UPDATE ab und ruft hier
process_update() auf — dieselbe Single-Source-of-Truth wie Cron + Nachhoer-Loop
(scripts/telegram_check.py). Keine Logik-Duplikation.

Aufruf:  WEBHOOK_UPDATE='<update-json>'  python scripts/process_webhook_update.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ importierbar machen


def _run(raw: str, load_secret, processor) -> str:
    """Parst das Update-JSON und reicht es an processor(update, chat_id) weiter.

    Reine Verdrahtung mit injizierten Abhaengigkeiten (load_secret, processor),
    damit der Pfad ohne Netz/echte Secrets testbar ist (siehe
    test_process_webhook_update.py).

    Returns:
        Der Status von processor(...) ("handled"/"skipped"/"launched"), oder
        "skipped" wenn kein Update anliegt.
    """
    if not raw or not raw.strip():
        print("Kein WEBHOOK_UPDATE gesetzt — nichts zu tun.")
        return "skipped"
    update = json.loads(raw)
    own_chat_id = str(load_secret("TELEGRAM_CHAT_ID"))
    return processor(update, own_chat_id)


def main() -> None:
    # Importe absichtlich in main(): haelt den Modul-Import schwergewichtsfrei,
    # sodass _run() ohne requests/telegram-Stack getestet werden kann.
    from telegram_bot import _load_secret
    from telegram_check import process_update

    _run(os.environ.get("WEBHOOK_UPDATE", ""), _load_secret, process_update)


if __name__ == "__main__":
    main()
