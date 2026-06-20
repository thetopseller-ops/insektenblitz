# Content-Maschine — Bedienungsanleitung

Diese Anleitung erklärt das automatische Blog-System der Insektenblitz-Website.
Sie ist für Nicht-Techniker geschrieben — du brauchst kein Programmier-Wissen.

---

## 1. Was das System tut

Jeden Morgen sucht das System automatisch nach aktuellen Nachrichten zum
Eichenprozessionsspinner (EPS), lässt daraus von einer KI (künstliche Intelligenz,
hier: Claude) einen fertigen Blogpost-Entwurf schreiben und schickt dir eine
**Vorschau per Telegram** (Messenger-App). Du prüfst den Entwurf und entscheidest
per Knopfdruck:

- **Freigeben** → der Beitrag wird veröffentlicht (beim nächsten Prüf-Lauf, der alle
  15 Minuten läuft — oder sofort von Hand, siehe Abschnitt 3). Er erscheint dann auf
  der Website, wird automatisch auf der **Startseite** verlinkt und in die
  **Google-Sitemap** eingetragen; du bekommst eine Telegram-Nachricht mit klickbarem Link.
- **Verwerfen** → der Entwurf wird gelöscht, nichts wird veröffentlicht.

Nichts wird ohne deine Freigabe veröffentlicht. Du behältst immer die Kontrolle.

---

## 2. Einmal einrichten: die 4 Zugangsdaten („Secrets")

Damit das System arbeiten kann, müssen vier Zugangsdaten **einmalig** im
GitHub-Projekt hinterlegt werden. „Secrets" (englisch für Geheimnisse) sind
geschützte Werte, die niemand außer dem System sehen kann — sie stehen **nie**
im sichtbaren Code.

**Klick-für-Klick auf GitHub:**
1. Öffne das Projekt auf GitHub.
2. Oben auf **Settings** (Einstellungen) klicken.
3. Links im Menü auf **Secrets and variables** → **Actions** klicken.
4. Auf den grünen Knopf **New repository secret** klicken.
5. Für jeden der vier Einträge unten: Namen exakt eintippen, Wert einfügen, **Add secret**.

| Name (exakt so eintippen) | Was ist das? | Woher bekommst du den Wert? |
|---------------------------|--------------|------------------------------|
| `ANTHROPIC_API_KEY` | Zugang zur KI, die die Texte schreibt | Anthropic Console (console.anthropic.com → API Keys) |
| `TELEGRAM_BOT_TOKEN` | Zugang zum Telegram-Bot, der dir die Vorschau schickt | Vom „BotFather" in Telegram (beim Anlegen des Bots) |
| `TELEGRAM_CHAT_ID` | Deine persönliche Chat-Nummer (damit nur DU Vorschauen bekommst und freigeben kannst) | Deine eigene Telegram-Chat-ID |
| `SITE_BASE_URL` | Die Web-Adresse der Website (für den Vorschau-Link) | z. B. `https://insektenblitz.de` oder die Demo-Adresse |

> Hinweis: Ein fünfter Zugang (`GH_PAT`) ist **nicht** nötig — GitHub stellt dem
> System dafür automatisch ein eingebautes Zugriffsrecht bereit.

---

## 3. Betrieb: so läuft es im Alltag

**Automatisch (täglich):** Das System startet jeden Tag um **06:07 UTC**
(= 08:07 Uhr deutsche Sommerzeit) von selbst und schickt dir die Vorschau.
Du musst dafür nichts tun. Nach jedem Lauf kommt zusätzlich eine kurze
**„Lauf OK"-Nachricht** in Telegram (so siehst du, dass die Automatik läuft) —
bei einem Fehler stattdessen eine Fehlermeldung.

**Manuell starten (jederzeit) — zwei Wege:**

*Weg 1 — per Telegram (am bequemsten):* Schick dem Bot einfach **`/neuerpost`**
(oder **`/neuerpost Goldafter`** für ein bestimmtes Thema). Der Befehl wird beim
nächsten Post-Approval-Check-Lauf erkannt (alle 15 Minuten) und startet dann die
Generierung. Aus Sicherheitsgründen funktioniert das **nur von deiner eigenen
Chat-ID** — niemand sonst kann auf deine Kosten einen Beitrag auslösen.

*Weg 2 — über GitHub Actions:*
1. Auf GitHub oben auf den Tab **Actions** klicken.
2. Links den Ablauf **Daily Content** wählen.
3. Rechts auf **Run workflow** klicken.
4. Optional: ins Feld **thema** ein Wunschthema eintippen (leer lassen = aktuelle News).
5. Grünen **Run workflow**-Knopf drücken → kurz warten → die Vorschau kommt per Telegram.

**Freigeben oder Verwerfen:** In der Telegram-Vorschau auf **Freigeben** oder
**Verwerfen** tippen. Ein zweiter Ablauf namens **Post Approval Check** prüft
automatisch, ob du geklickt hast, und führt die Aktion aus. Er ist auf alle
15 Minuten eingestellt — GitHub kann diese automatischen Läufe bei kostenlosen
Projekten aber verzögern; in der Praxis kann es daher **bis zu ~1 Stunde** dauern,
bis ein freigegebener Beitrag von allein online ist (für einen Blog völlig in Ordnung).
**Soll es sofort gehen** (z. B. bei einer Vorführung), löse den Check von Hand aus:
Actions → **Post Approval Check** → **Run workflow** → in Sekunden live.

---

## 4. Wenn etwas nicht klappt (Troubleshooting)

**Es kommt keine Vorschau in Telegram an?**
1. Auf GitHub den Tab **Actions** öffnen.
2. Den letzten **Daily Content**-Lauf anklicken.
3. Ist der Punkt **rot** (Kreuz) statt **grün** (Haken)? Dann gab es einen Fehler —
   den Lauf anklicken und die Log-Meldung (Protokoll) lesen.

Häufige Ursachen:
- Ein **Secret fehlt oder ist falsch** geschrieben → Schritt 2 prüfen (Name exakt? Wert korrekt?).
- Das **ANTHROPIC_API_KEY**-Guthaben ist leer → in der Anthropic Console prüfen.

**Freigabe-Klick passiert nichts?**
- Bis zu 15 Minuten warten (der Check läuft im 15-Minuten-Takt, manchmal später), **oder**
- unter Actions → **Post Approval Check** → **Run workflow** den Check sofort starten.
- **Häufigste Ursache:** Läuft auf einem Rechner noch ein **lokales Bot-Programm**
  (ein offenes `python`-Fenster mit dem Bot)? Telegram liefert jeden Klick **nur
  einmal** aus — ein lokales Programm fängt ihn ab, bevor die Cloud ihn sieht, und der
  Check meldet dann „Keine Updates". Im Betrieb deshalb **kein lokales Bot-Programm
  laufen lassen** (im Task-Manager prüfen, dass kein `python.exe` aktiv ist), dann erneut
  freigeben und den Check starten.

---

## 5. Übergabe-Hinweis (für den Echtbetrieb bei Malte)

Dieses System kam per Pull Request (Code-Vorschlag) aus Erions Test-Kopie des Projekts.
Für den dauerhaften Echtbetrieb auf Maltes eigenem Konto werden dieselben vier Secret-Namen
verwendet, aber mit **Maltes eigenen Werten**:

- eigener **TELEGRAM_BOT_TOKEN** + eigene **TELEGRAM_CHAT_ID** (Maltes Bot/Chat),
- eigener **ANTHROPIC_API_KEY** (Maltes KI-Zugang),
- eigene **SITE_BASE_URL** (die echte Website-Adresse).

Die Namen bleiben gleich — nur die hinterlegten Werte ändern sich. Danach läuft das
System vollständig auf Maltes Seite, ohne Erion.

---

## Bekanntes Backlog (nach Deadline)

Die folgenden drei Punkte wurden im Audit (D-15) als bewusst auf nach den
Festpreis-Liefertermin verschoben erfasst. Sie verbessern die Langzeit-Wartbarkeit,
sind aber nicht nötig, damit das System zuverlässig läuft.

**1. Automatisierte Test-Suite (pytest)**
CONCERNS markiert fehlende Tests als HIGH-Risiko. Eine pytest-Suite würde künftige
Änderungen absichern und Regressionen früh erkennen. Empfehlung nach der Deadline:
Unit-Tests für die kritischen Pfade (Slug-Erstellung, Evergreen-Fallback, Approve-Logik).

**2. Strukturiertes Logging**
Alle Statusausgaben laufen aktuell über `print()`. Für Produktionsbetrieb wäre
`logging` (Python-Standardbibliothek) besser: einstellbare Log-Level, Timestamps,
einfacheres Durchsuchen der GitHub-Actions-Logs.

**3. Externes Uptime-Monitoring**
Der tägliche Health-Ping (Telegram-Nachricht bei jedem Lauf) zeigt an, ob der
daily-content-Lauf erfolgreich war. Ein zusätzlicher externer Dienst wie
Healthchecks.io oder UptimeRobot würde stille Ausfälle erkennen (z. B. wenn
GitHub Actions den Cron-Lauf überspringt). Kostenlos verfügbar für diesen
Anwendungsfall.
