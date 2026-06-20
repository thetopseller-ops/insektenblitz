"""Behavior-Tests fuer den Nachhoer-Loop (Phase 04.1, Plan 01, Task 3).

Die Loop-Tests rufen die ECHTE content_machine.nachhoer_loop() auf (kein Nachbau),
damit Regressionen im Produktionscode auffallen.

Prueft:
  1. Approve im Fenster -> _do_approve genau einmal, Loop endet terminal (AUTO-01)
  2. Reject im Fenster -> _do_reject genau einmal, nichts live, Loop endet (AUTO-02)
  3. Fremde Chat-ID ignoriert -> weder _do_approve noch _do_reject (AUTO-04)
  4. Timeout sauber -> Loop endet ohne Exception, _do_approve/_do_reject nie (AUTO-03)
  5. Keine Doppelverarbeitung -> _do_approve genau einmal, Offset fortgeschrieben (AUTO-03)
  6. WR-02: Stale Backlog-Klick loest den neuen Post NICHT aus; frischer Klick schon.

Alle externen Effekte sind gemockt (kein Netz, kein Repo, kein Telegram).
Aufruf: python -m unittest scripts.test_nachhoer_loop -v
"""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# scripts/ importierbar machen (analog zur Produktionsumgebung)
sys.path.insert(0, str(Path(__file__).resolve().parent))


# ---------------------------------------------------------------------------
# Hilfsfunktionen fuer Update-Fixtures
# ---------------------------------------------------------------------------

def _make_cq_update(update_id: int, chat_id: str, from_id: str, data: str) -> dict:
    """Erzeugt ein realistisches callback_query-Update-Dict."""
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cq-{update_id}",
            "from": {"id": int(from_id)},
            "message": {
                "chat": {"id": int(chat_id)},
            },
            "data": data,
        },
    }


def _make_msg_update(update_id: int, chat_id: str, from_id: str, text: str) -> dict:
    """Erzeugt ein realistisches Text-Nachrichten-Update-Dict."""
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": int(chat_id)},
            "from": {"id": int(from_id)},
            "text": text,
        },
    }


OWN_CHAT_ID = "111111111"
FOREIGN_CHAT_ID = "999999999"
SLUG = "test-slug-2026"
DRAFT = "draft-2026-06-20.html"


# ---------------------------------------------------------------------------
# Tests fuer process_update() (Unit-Level)
# ---------------------------------------------------------------------------

class TestProcessUpdate(unittest.TestCase):
    """Testet process_update() direkt (Unit-Tests ohne Loop)."""

    def _patch_all(self):
        """Gibt einen dict mit allen noetigen Mock-Patchern zurueck."""
        return {
            "do_approve": patch("telegram_check._do_approve", return_value="Test-Titel"),
            "do_reject":  patch("telegram_check._do_reject"),
            "find_draft": patch("telegram_check._find_draft_in_repo", return_value=DRAFT),
            "get_upd":    patch("telegram_check.get_updates", return_value=[]),
            "send_msg":   patch("telegram_check.send_message"),
            "ans_cbq":    patch("telegram_check.answer_callback_query"),
            "load_sec":   patch("telegram_check._load_secret", return_value="https://insektenblitz.com"),
        }

    def test_approve_eigene_chat_id(self):
        """Approve-Klick von eigener Chat-ID -> _do_approve einmal, 'handled' zurueck."""
        upd = _make_cq_update(1, OWN_CHAT_ID, OWN_CHAT_ID, f"approve:{SLUG}")
        patches = self._patch_all()
        with patches["do_approve"] as m_approve, \
             patches["do_reject"]  as m_reject, \
             patches["find_draft"], \
             patches["get_upd"], \
             patches["send_msg"], \
             patches["ans_cbq"], \
             patches["load_sec"]:
            from telegram_check import process_update
            result = process_update(upd, OWN_CHAT_ID)
        self.assertEqual(result, "handled")
        m_approve.assert_called_once()
        m_reject.assert_not_called()

    def test_reject_eigene_chat_id(self):
        """Reject-Klick von eigener Chat-ID -> _do_reject einmal, 'handled' zurueck."""
        upd = _make_cq_update(2, OWN_CHAT_ID, OWN_CHAT_ID, f"reject:{SLUG}")
        patches = self._patch_all()
        with patches["do_approve"] as m_approve, \
             patches["do_reject"]  as m_reject, \
             patches["find_draft"], \
             patches["get_upd"], \
             patches["send_msg"], \
             patches["ans_cbq"], \
             patches["load_sec"]:
            from telegram_check import process_update
            result = process_update(upd, OWN_CHAT_ID)
        self.assertEqual(result, "handled")
        m_reject.assert_called_once()
        m_approve.assert_not_called()

    def test_fremde_chat_id_ignoriert(self):
        """Approve-Klick von fremder Chat-ID -> weder _do_approve noch _do_reject."""
        upd = _make_cq_update(3, FOREIGN_CHAT_ID, FOREIGN_CHAT_ID, f"approve:{SLUG}")
        patches = self._patch_all()
        with patches["do_approve"] as m_approve, \
             patches["do_reject"]  as m_reject, \
             patches["find_draft"], \
             patches["get_upd"], \
             patches["send_msg"], \
             patches["ans_cbq"], \
             patches["load_sec"]:
            from telegram_check import process_update
            result = process_update(upd, OWN_CHAT_ID)
        self.assertEqual(result, "skipped")
        m_approve.assert_not_called()
        m_reject.assert_not_called()


# ---------------------------------------------------------------------------
# Tests fuer den Nachhoer-Loop in content_machine (Verhalten des Loops)
# ---------------------------------------------------------------------------

def _run_loop_with_updates(updates_sequence, backlog=None, budget_s=0.2, long_poll_s=0):
    """Fuehrt den ECHTEN content_machine.nachhoer_loop() mit gemockten Abhaengigkeiten aus.

    Testet damit den Produktionscode selbst (nicht eine Nachbildung) — siehe IN-01.

    backlog:          Rueckgabe des einmaligen Backlog-Peeks am Loop-Start (WR-02-Anker).
                      Default None -> leerer Backlog (Normalfall, Anker bei offset=0).
    updates_sequence: Liste von Listen — Rueckgaben der folgenden Long-Poll-Aufrufe.
                      Leer/erschoepft = Timeout.
    Gibt (m_approve, m_reject, m_get_updates, handled) zurueck.
    """
    import content_machine as cm
    import telegram_check as tc

    m_approve  = MagicMock(return_value="Gemockter Titel")
    m_reject   = MagicMock()
    m_find     = MagicMock(return_value=DRAFT)
    m_send_msg = MagicMock()
    m_ans_cbq  = MagicMock()
    m_load_sec = MagicMock(return_value=OWN_CHAT_ID)

    # Erster get_updates-Aufruf = Backlog-Peek; danach die Sequenz; dann immer [].
    poll_returns = iter([backlog or []] + list(updates_sequence))
    def _get_upd_side_effect(offset=0, long_poll=0):
        try:
            return next(poll_returns)
        except StopIteration:
            return []
    m_get_updates = MagicMock(side_effect=_get_upd_side_effect)

    with patch.object(tc, "_do_approve", m_approve), \
         patch.object(tc, "_do_reject",  m_reject), \
         patch.object(tc, "_find_draft_in_repo", m_find), \
         patch.object(tc, "get_updates",  m_get_updates), \
         patch.object(tc, "send_message", m_send_msg), \
         patch.object(tc, "answer_callback_query", m_ans_cbq), \
         patch.object(tc, "_load_secret", m_load_sec), \
         patch.object(cm, "get_updates", m_get_updates):
        handled = cm.nachhoer_loop(str(OWN_CHAT_ID), budget_s=budget_s, long_poll_s=long_poll_s)

    return m_approve, m_reject, m_get_updates, handled


class TestNachhoerLoop(unittest.TestCase):
    """Behavior-Tests fuer den Nachhoer-Loop (AUTO-01..04)."""

    def test_approve_im_fenster(self):
        """AUTO-01: Approve-Klick im Fenster -> _do_approve genau einmal, Loop endet terminal."""
        approve_upd = _make_cq_update(10, OWN_CHAT_ID, OWN_CHAT_ID, f"approve:{SLUG}")
        m_approve, m_reject, _, handled = _run_loop_with_updates([[approve_upd]])
        m_approve.assert_called_once()
        m_reject.assert_not_called()
        self.assertTrue(handled, "Loop muss nach Approve als 'handled' beendet sein")

    def test_reject_im_fenster(self):
        """AUTO-02: Reject-Klick im Fenster -> _do_reject genau einmal, nichts live, Loop endet."""
        reject_upd = _make_cq_update(20, OWN_CHAT_ID, OWN_CHAT_ID, f"reject:{SLUG}")
        m_approve, m_reject, _, handled = _run_loop_with_updates([[reject_upd]])
        m_reject.assert_called_once()
        m_approve.assert_not_called()
        self.assertTrue(handled, "Loop muss nach Reject als 'handled' beendet sein")

    def test_fremde_chat_id_ignoriert(self):
        """AUTO-04: Fremde Chat-ID -> weder _do_approve noch _do_reject; Loop laeuft bis Timeout."""
        foreign_upd = _make_cq_update(30, FOREIGN_CHAT_ID, FOREIGN_CHAT_ID, f"approve:{SLUG}")
        # budget_s sehr kurz: Loop soll durch Timeout enden, nicht durch handled
        m_approve, m_reject, _, handled = _run_loop_with_updates(
            [[foreign_upd], [], []], budget_s=0.1
        )
        m_approve.assert_not_called()
        m_reject.assert_not_called()
        self.assertFalse(handled, "Loop darf bei fremder Chat-ID NICHT als 'handled' beendet sein")

    def test_timeout_sauber(self):
        """AUTO-03: Kein Klick -> Loop endet nach Zeitbudget ohne Exception."""
        # Nur leere Update-Listen = simulierter Timeout
        try:
            m_approve, m_reject, _, handled = _run_loop_with_updates(
                [[], [], []], budget_s=0.1
            )
        except Exception as exc:
            self.fail(f"Loop warf Exception beim Timeout: {exc}")
        m_approve.assert_not_called()
        m_reject.assert_not_called()
        self.assertFalse(handled, "Loop darf beim Timeout NICHT als 'handled' beendet sein")

    def test_keine_doppelverarbeitung(self):
        """AUTO-03: Ein verarbeitetes Update wird genau einmal verarbeitet.

        Approve kommt im Fenster an; danach liefern weitere Polls nichts. _do_approve
        muss trotz mehrerer moeglicher Iterationen genau einmal aufgerufen werden, und
        der Loop terminiert sofort bei 'handled'."""
        approve_upd = _make_cq_update(10, OWN_CHAT_ID, OWN_CHAT_ID, f"approve:{SLUG}")
        m_approve, m_reject, m_get, handled = _run_loop_with_updates(
            [[approve_upd], [], []], budget_s=0.5
        )
        m_approve.assert_called_once()
        m_reject.assert_not_called()
        self.assertTrue(handled)
        # Long-Poll nach dem Approve muss Offset 11 (= update_id+1) verwenden — Single-Delivery.
        poll_offsets = [c.kwargs.get("offset") for c in m_get.call_args_list]
        self.assertIn(11, poll_offsets, "Offset muss nach Approve auf update_id+1 fortgeschrieben sein")

    def test_wr02_stale_backlog_wird_nicht_verarbeitet(self):
        """WR-02: Ein alter, unbestaetigter Klick im Backlog darf den NEUEN Post nicht
        veroeffentlichen. Der Loop verankert sich hinter dem Backlog; nur Klicks, die
        WAEHREND des Fensters eintreffen, zaehlen."""
        stale = _make_cq_update(5, OWN_CHAT_ID, OWN_CHAT_ID, "approve:alter-post-slug")
        m_approve, m_reject, m_get, handled = _run_loop_with_updates(
            [], backlog=[stale], budget_s=0.1
        )
        m_approve.assert_not_called()
        m_reject.assert_not_called()
        self.assertFalse(handled, "Stale Backlog-Klick darf den neuen Post nicht ausloesen")
        # Peek war offset=0; erster Long-Poll danach muss hinter dem Backlog (>=6) verankern.
        poll_offsets = [c.kwargs.get("offset") for c in m_get.call_args_list]
        self.assertEqual(poll_offsets[0], 0, "Erster Aufruf ist der Backlog-Peek (offset=0)")
        self.assertGreaterEqual(poll_offsets[1], 6, "Loop muss hinter dem Backlog verankern")

    def test_wr02_neuer_klick_nach_backlog_wird_verarbeitet(self):
        """WR-02-Gegenprobe: Trotz vorhandenem Backlog wird ein FRISCHER Klick (neuere
        update_id, waehrend des Fensters) korrekt verarbeitet."""
        stale = _make_cq_update(5, OWN_CHAT_ID, OWN_CHAT_ID, "approve:alter-slug")
        fresh = _make_cq_update(6, OWN_CHAT_ID, OWN_CHAT_ID, f"approve:{SLUG}")
        m_approve, m_reject, _, handled = _run_loop_with_updates(
            [[fresh]], backlog=[stale]
        )
        m_approve.assert_called_once()
        m_reject.assert_not_called()
        self.assertTrue(handled, "Frischer Klick im Fenster muss verarbeitet werden")


class TestRedaction(unittest.TestCase):
    """WR-01: Secrets werden VOR dem Kuerzen geschwaerzt (kein Leak durch Schnitt)."""

    def test_token_nahe_position_200_wird_geschwaerzt(self):
        import content_machine as cm
        token = "123456789:" + "A" * 40  # realistisches Telegram-Bot-Token-Muster
        # Token so platzieren, dass es bei "erst [:200], dann schwaerzen" zerschnitten wuerde.
        raw = ("x" * 190) + token + " danach"
        out = cm._redact_secrets(raw)[:200]
        self.assertNotIn(token, out, "Vollstaendiges Token darf nie im Output stehen")
        self.assertNotIn("123456789:AAAA", out, "Auch kein Token-Anfang darf durchrutschen")
        self.assertIn("<redacted-token>", cm._redact_secrets(raw))


if __name__ == "__main__":
    unittest.main()
