"""Selbsttest fuer den Webhook-Einstieg (_run): JSON-Parse + korrekte Weitergabe.

Kein Netz, keine echten Secrets — process_update und _load_secret werden injiziert.
Lauf:  python scripts/test_process_webhook_update.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from process_webhook_update import _run


def test_parst_und_reicht_update_weiter():
    calls = []
    raw = '{"update_id": 42, "callback_query": {"data": "approve:foo"}}'
    result = _run(raw, lambda k: "12345", lambda upd, cid: calls.append((upd, cid)) or "handled")
    assert result == "handled", result
    assert len(calls) == 1, calls
    upd, cid = calls[0]
    assert upd["update_id"] == 42, upd
    assert upd["callback_query"]["data"] == "approve:foo", upd
    assert cid == "12345", cid  # chat_id als String an process_update


def test_leeres_update_ueberspringt():
    calls = []
    result = _run("", lambda k: "12345", lambda upd, cid: calls.append(1) or "handled")
    assert result == "skipped", result
    assert calls == [], calls  # processor NICHT aufgerufen


if __name__ == "__main__":
    test_parst_und_reicht_update_weiter()
    test_leeres_update_ueberspringt()
    print("OK: process_webhook_update._run")
