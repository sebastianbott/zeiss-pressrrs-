# ZEISS Press Releases → RSS

Erzeugt automatisch (täglich) einen RSS-Feed aus den ZEISS Pressemitteilungen:
https://www.zeiss.com/corporate/en/about-zeiss/present/newsroom/press-releases.html

Die Seite lädt ihre Ergebnisliste per JavaScript aus einer internen Such-API
nach. Deshalb rendert `scrape.py` die Seite mit einem echten (headless)
Browser (Playwright) und liest die dargestellten Pressemitteilungen aus dem
Ergebnis-DOM aus – genau wie ein normaler Besucher sie sehen würde.

## Einrichtung (einmalig, ca. 5 Minuten)

1. Neues **privates oder öffentliches** GitHub-Repository anlegen (z. B.
   `zeiss-press-rss`) und diesen Ordner hochladen (alle Dateien inkl.
   `.github/workflows/update-feed.yml`).
2. Im Repo unter **Settings → Pages**:
   - Source: „Deploy from a branch"
   - Branch: `main`, Ordner: `/docs`
   - Speichern.
3. Im Repo unter **Settings → Actions → General → Workflow permissions**:
   - „Read and write permissions" aktivieren (damit die Action `feed.xml`
     committen darf).
4. Unter dem Tab **Actions** den Workflow „Update ZEISS press release RSS
   feed" einmal manuell starten (Button „Run workflow"), damit `feed.xml`
   das erste Mal erzeugt wird.
5. Nach ein paar Minuten ist der Feed erreichbar unter:
   `https://<dein-github-username>.github.io/<repo-name>/feed.xml`

   Diese URL kannst du in jedem RSS-Reader (Feedly, NetNewsWire, Outlook,
   etc.) abonnieren. Der Workflow läuft danach automatisch jeden Tag und
   aktualisiert die Datei.

## Wenn der Feed leer bleibt / die Action fehlschlägt

Ich konnte das Script hier nicht gegen die echte, gerenderte Seite testen
(kein Browser-Zugriff in meiner Umgebung). Falls die Action mit „Keine
Pressemitteilungen gefunden" fehlschlägt, hat ZEISS wahrscheinlich andere
CSS-Klassen/Struktur im Ergebnis-Bereich als angenommen:

1. Öffne die Seite in Chrome.
2. Rechtsklick auf eine Pressemitteilung in der Liste → „Untersuchen".
3. Schau dir die umschließenden Elemente an (Tag-Namen, Klassen).
4. Passe die Liste `CARD_SELECTOR_CANDIDATES` oben in `scrape.py`
   entsprechend an (füge den passenden Selektor als ersten Eintrag hinzu).

Sag mir gern die gefundene Struktur (z. B. per Copy-HTML aus den
DevTools), dann passe ich das Script dafür an.

## Lokal testen

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
python scrape.py
# Ergebnis liegt dann in docs/feed.xml
```
