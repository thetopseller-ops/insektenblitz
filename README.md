# insektenblitz
Hier liegt unsere Website zum EPS Projekt
[Erforderliche Ergänzungen vor Veröffentlichung.md](https://github.com/user-attachments/files/28924299/Erforderliche.Erganzungen.vor.Veroffentlichung.md)


> **Automatische Content-Maschine:** Diese Website hat ein automatisches System, das täglich
> einen Blogpost-Entwurf zum Eichenprozessionsspinner erstellt und nach Freigabe per Telegram
> live schaltet. Bedienung, Einrichtung und Betrieb stehen in **[CONTENT-MACHINE.md](CONTENT-MACHINE.md)**
> — verständlich erklärt, kein Programmier-Wissen nötig.

---

# Erforderliche Ergänzungen vor Veröffentlichung
### Insektenblitz – insektenblitz.de
*Stand: Juni 2026 — vollständige Checkliste, kein Punkt darf fehlen*

---

## 1. Kontaktdaten & Firmendaten

- [ ] **Telefonnummer eintragen** — aktueller Platzhalter: `+49 123 456789`
  - Muss an folgenden Stellen in `index.html` ersetzt werden: Hero-Button, alle drei Schädlings-Karten, alle drei Leistungs-Karten, CTA-Banner über dem Footer, Footer, JSON-LD-Schema ganz oben im Code
- [ ] **Vollständige Firmenadresse im Footer eintragen** — aktueller Platzhalter: `[VOLLSTÄNDIGE ADRESSE]`
- [ ] **Öffnungszeiten** — aktueller Platzhalter: `[ÖFFNUNGSZEITEN OPTIONAL]` — entweder echte Zeiten eintragen oder den Eintrag komplett entfernen
- [ ] **E-Mail-Adresse prüfen** — `info@insektenblitz.de` steht drin, muss aber tatsächlich erreichbar sein (Domain + Postfach einrichten, siehe Punkt 3)

---

## 2. Rechtliche Pflichtseiten (für Deutschland verpflichtend)

- [ ] **Impressum erstellen** — Datei `impressum.html` anlegen und befüllen mit:
  - Vollständiger Name des Inhabers oder der Geschäftsführung
  - Vollständige Firmenadresse (Straße, PLZ, Ort)
  - Telefonnummer
  - E-Mail-Adresse
  - Umsatzsteuer-Identifikationsnummer (USt-IdNr.) — falls vorhanden
  - Handelsregisternummer (HRB) und Registergericht — falls eingetragen
  - Vertretungsberechtigte Person (bei GmbH, UG etc.)
  - Hinweis auf Berufsaufsichtsbehörde — falls in der Schädlingsbekämpfung relevant
- [ ] **Datenschutzerklärung erstellen** — Datei `datenschutz.html` anlegen und befüllen mit:
  - Wer ist verantwortlich (Name, Adresse)
  - Welche Daten werden erhoben (Besucherdaten, Anruf-Tracking, etc.)
  - Google Fonts: aktuell wird von Google-Servern geladen — muss erwähnt werden
  - Anruf-Tracking (das eingebaute Tool speichert Klick-Daten im Browser) — erwähnen
  - WhatsApp-Button — Hinweis, dass Klick zu WhatsApp weiterleitet
  - Rechte der Nutzer (Auskunft, Löschung etc.)
  - Kontakt des Datenschutzbeauftragten (falls nötig)
- [ ] **AGB erstellen oder Link entfernen** — im Footer gibt es einen AGB-Link, der aktuell auf `#` zeigt (ins Leere). Entweder AGB schreiben und als eigene Seite ablegen, oder den Link entfernen wenn keine AGBs erforderlich sind
- [ ] **Cookie-Hinweis / Consent-Banner einbauen** — die Website lädt Google Fonts von externen Google-Servern, das überträgt die IP-Adresse des Besuchers an Google und ist ohne Einwilligung in Deutschland rechtlich problematisch. Lösung: entweder Banner einbauen oder (besser):
- [ ] **Google Fonts lokal hosten** — Schriftarten einmalig herunterladen und im eigenen Hosting ablegen, statt sie von `fonts.googleapis.com` zu laden. Dann entfällt das Cookie-Problem komplett. Fonts: Merriweather (300, 400, 700) und Open Sans (400, 500, 600, 700)

---

## 3. Domain & Hosting

- [ ] **Domain `insektenblitz.de` registrieren** — prüfen ob die Domain noch verfügbar ist, bei einem deutschen Registrar (z.B. IONOS, Strato, Hetzner, Namecheap) registrieren
- [ ] **Webhosting einrichten** — da die Website nur aus HTML/CSS/JS besteht, reicht einfachstes Webhosting (kein PHP, kein Server nötig). Günstige Optionen: Hetzner, IONOS, Netlify (kostenlos), GitHub Pages (kostenlos)
- [ ] **Alle Dateien hochladen** — `index.html` + gesamten `images/`-Ordner auf den Hoster laden
- [ ] **SSL-Zertifikat aktivieren** — HTTPS ist Pflicht (Sicherheit, SEO, Seriösität). Die meisten Hoster stellen Let's Encrypt kostenlos zur Verfügung, einfach im Hoster-Panel aktivieren
- [ ] **E-Mail-Postfach `info@insektenblitz.de` einrichten** — beim Domainanbieter oder einem separaten Mail-Anbieter (z.B. Google Workspace, Posteo)

---

## 4. Bilder ersetzen

- [ ] **Hero-Hintergrundbild** (`images/hero-eps-finka.jpg`) — aktuell ein Platzhalter-Foto aus Kronberg/Taunus (kein Finka-Hintergrund). Ersetzen durch: eigenes Foto eines EPS-Nests in einem Baum mit spanischer Finka im Hintergrund
- [ ] **Teamfoto** (`images/about-team.jpg`) — aktuell ein KI-generiertes Bild (sehr klein, 15 KB). Ersetzen durch: echtes Foto des Gründers oder Teams, am besten mit Drohne und im Freien
- [ ] **Kinder-Bild** (`images/alert-kinder.jpg`) — KI-generiert. Bei Bedarf durch lizenzfreies Echte-Foto ersetzen
- [ ] **Familie-Bild** (`images/blog-2-familie.jpg`) — KI-generiert. Bei Bedarf durch lizenzfreies Echtes Foto ersetzen
- [ ] **Favicon erstellen und einbinden** — aktuell hat die Website kein Icon im Browser-Tab und im Lesezeichen. Das Logo (goldener Blitz auf Grün) als 32×32px `.ico` oder `.svg` exportieren und im `<head>` der index.html einbinden:
  ```html
  <link rel="icon" href="images/logo-insektenblitz.svg" type="image/svg+xml">
  ```

---

## 5. Fallbeispiele aktivieren (Sektion aktuell versteckt)

Die gesamte Sektion „Echte Ergebnisse" ist mit `display:none` ausgeblendet und enthält nur Platzhalter.

- [ ] **Echte Vorher-/Nachher-Fotos für alle drei Fallbeispiele bereitstellen und einfügen:**
  - Fallbeispiel 1 (Grundschule München): `[BILD-CASE-1-VORHER]` und `[BILD-CASE-1-NACHHER]`
  - Fallbeispiel 2 (Privatgarten Rosenheim): `[BILD-CASE-2-VORHER]` und `[BILD-CASE-2-NACHHER]`
  - Fallbeispiel 3 (Finca Mallorca): `[BILD-CASE-3-VORHER]` und `[BILD-CASE-3-NACHHER]`
- [ ] **Fallbeispiel-Texte auf echte Kundenprojekte anpassen** — Ort, Baum-Anzahl, Nester-Anzahl, Einsatzdauer, Ergebnis. Derzeit sind das fiktive Beispieldaten
- [ ] **Statistiken prüfen** — Zahlen wie „47 Nester", „4h Einsatzdauer", „48h bis Freigabe" müssen der Realität entsprechen
- [ ] **Sektion sichtbar schalten** — in `index.html` bei der Zeile `<section class="section" style="background: white; display: none;" id="cases">` den Teil `display: none;` entfernen

---

## 6. Kundenbewertungen aktivieren (Sektion aktuell versteckt)

Die Testimonials-Sektion ist mit `display:none` ausgeblendet und enthält nur Platzhalter.

- [ ] **Mindestens 3 echte Kundenbewertungen einholen** — vorher schriftliche Erlaubnis der Kunden einholen, den Namen und das Zitat zu verwenden
- [ ] **Platzhalter befüllen:**
  - `[TESTIMONIAL-1-TEXT]` bis `[TESTIMONIAL-4-TEXT]` → echte Kundenzitate
  - `[KUNDE-1-NAME], [ORT]` bis `[KUNDE-4-NAME], [ORT]` → echte Namen und Orte (oder anonymisiert, z.B. „Familie K. aus München")
  - Kundenfotos oder neutrale Avatare einbinden (statt der leeren Platzhalter-Felder)
- [ ] **Sektion sichtbar schalten** — bei `<section class="section" id="testimonials" style="display: none;">` den Teil `display: none;` entfernen

---

## 7. Blog-Artikel schreiben

Die drei Blog-Karten sind sichtbar, aber die Links führen ins Leere (`href="#"`).

- [ ] **Artikel 1 schreiben:** „Eichenprozessionsspinner 2025: Warum der Befall immer früher beginnt" — als eigene HTML-Seite anlegen (z.B. `blog-eps-saison-2025.html`) und Link in der Blog-Karte aktualisieren
- [ ] **Artikel 2 schreiben:** „Gifthaare im Garten: So schützen Sie Kinder und Haustiere richtig" — als eigene HTML-Seite anlegen und Link aktualisieren
- [ ] **Artikel 3 schreiben:** „Palmenzünsler auf Mallorca: 5 Warnzeichen, die Sie kennen müssen" — als eigene HTML-Seite anlegen und Link aktualisieren
- [ ] **Alternativ:** Links entfernen oder als „Bald verfügbar" kennzeichnen, wenn die Artikel noch nicht fertig sind

---

## 8. Inhalte inhaltlich prüfen und freigeben

- [ ] **Gründungsgeschichte prüfen** — die Geschichte von „dem Nachbarskind, das nach dem Spielen unter einer Eiche mit Hautausschlag ins Krankenhaus musste" steht im Über-Uns-Bereich. Stimmt das mit der echten Firmengeschichte überein? Falls nicht → Text anpassen
- [ ] **Teamvorstellung** — aktuell werden „Biologen, Drohnenpiloten & KI-Entwickler" erwähnt. Stimmt das mit dem echten Team überein? Falls gewünscht, echte Teammitglieder mit Namen vorstellen
- [ ] **„99% weniger Pestizide"-Aussage absichern** — diese Zahl ist ein starkes Verkaufsargument, kann aber bei Behörden oder kritischen Kunden hinterfragt werden. Entweder mit einer eigenen Messung belegen oder die Formulierung anpassen
- [ ] **„Kostenlose Erstberatung" bestätigen** — sicherstellen, dass das tatsächlich angeboten wird und betrieblich umsetzbar ist
- [ ] **Reaktionszeit-Versprechen prüfen** — im FAQ steht „Bei akutem Befall priorisieren wir Ihre Anfrage". Ist das operativ sicherstellbar, auch in der Hauptsaison?
- [ ] **Einsatzgebiet festlegen und kommunizieren** — aktuell wird angegeben: Deutschland, Österreich, Schweiz, Mallorca, Spanien. Ist das realistisch? Falls nicht, eingrenzen

---

## 9. Technische Ergänzungen für SEO und Social Media

- [ ] **Open Graph Meta-Tags ergänzen** — damit beim Teilen des Links auf WhatsApp, Facebook oder LinkedIn ein ansprechendes Vorschaubild erscheint. Folgendes in den `<head>` der index.html einfügen (Werte anpassen):
  ```html
  <meta property="og:title" content="Insektenblitz – Drohnen Nestbekämpfung">
  <meta property="og:description" content="Präzise, biologisch, sicher für Kinder & Haustiere.">
  <meta property="og:image" content="https://insektenblitz.de/images/hero-eps-finka.jpg">
  <meta property="og:url" content="https://insektenblitz.de">
  <meta property="og:type" content="website">
  ```
- [ ] **WhatsApp-Teilen-Link aktualisieren** — sobald die echte Domain steht, die URL `https://insektenblitz.de` im WhatsApp-Sharing-Link gegen die echte Live-URL tauschen (im `<a class="wa-share">`-Element in index.html)
- [ ] **Vor dem Launch robots-Tag vorübergehend auf noindex setzen** — solange die Seite noch unfertig ist, Google fernhalten: `<meta name="robots" content="noindex, nofollow">`. Nach dem Launch wieder auf `index, follow` zurücksetzen
- [ ] **Nach dem Launch: Google Search Console einrichten** — Seite dort anmelden, damit Google sie schnell indexiert und man Fehler sehen kann
- [ ] **Nach dem Launch: Google Business Profile anlegen** — kostenlosen Google-Maps-Eintrag für Insektenblitz anlegen mit Adresse, Telefon, Website und Fotos. Enorm wichtig für lokale Sichtbarkeit

---

## 10. Abschließende Qualitätskontrolle vor dem Launch

- [ ] **Alle Telefon-Links testen** — auf dem Handy: klickt man auf „Jetzt anrufen", wird die richtige Nummer gewählt?
- [ ] **Alle E-Mail-Links testen** — öffnet sich die Mail-App mit der richtigen Adresse?
- [ ] **Alle internen Links testen** — Navigation (Home, Über Uns, Schädlinge, Leistungen), Footer-Links
- [ ] **Impressum- und Datenschutz-Link testen** — zeigen sie auf die fertigen Seiten?
- [ ] **Website auf dem Handy testen** — mobiler Aufruf, alle Buttons klickbar, kein Text abgeschnitten
- [ ] **Website in Safari, Chrome und Firefox testen**
- [ ] **Ladezeit testen** — unter `pagespeed.web.dev` die URL eingeben und Ergebnis prüfen. Ziel: über 80 Punkte auf Mobilgeräten

---

*Alle Punkte dieser Liste müssen erledigt sein, bevor die Website öffentlich zugänglich gemacht und beworben wird.*
