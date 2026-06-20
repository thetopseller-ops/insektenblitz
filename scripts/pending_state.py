"""Lesen und Schreiben des Pending-State (.telegram-pending.json).

State-Felder (D-08, bereinigt D-14):
  - draft_filename : str   — Dateiname des Drafts (z.B. "draft-2026-06-18.html")
  - slug           : str   — URL-Slug des Posts
  - title          : str   — Titel des Posts

Entfernt (D-14): message_id und offset waren nie von telegram_check.py gelesen
(der Check ist state-frei und arbeitet direkt mit dem Repo + callback_data).

Die Datei liegt im Repo-Root und ist via .gitignore ignoriert (nie ins oeffentliche Repo).
"""
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / ".telegram-pending.json"
_REQUIRED_FIELDS = ("draft_filename", "slug", "title")


def write_pending(state: dict) -> None:
    """Schreibt den Pending-State in .telegram-pending.json.

    Args:
        state: Dict mit den D-08-Feldern (draft_filename, slug, title).
    """
    # Atomar schreiben (Temp + os.replace): ein Abbruch hinterlaesst nie eine
    # halb geschriebene/korrupte State-Datei (WR-06).
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, STATE_FILE)


def read_pending() -> "dict | None":
    """Liest den Pending-State aus .telegram-pending.json.

    Returns:
        State-Dict, oder None wenn keine Datei vorhanden ODER die Datei
        korrupt/unvollstaendig ist. Tolerant statt Crash (WR-02/03): der
        Loop behandelt None als "kein offener Draft".
    """
    if not STATE_FILE.exists():
        return None
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Pending-State unlesbar ({e}) — wird ignoriert.")
        return None
    if not isinstance(state, dict) or not all(f in state for f in _REQUIRED_FIELDS):
        print("  Pending-State unvollstaendig — wird ignoriert.")
        return None
    return state


def clear_pending() -> None:
    """Loescht .telegram-pending.json (nach Approve oder Reject in Plan 02).

    Kein Fehler wenn Datei nicht existiert.
    """
    if STATE_FILE.exists():
        STATE_FILE.unlink()
