# Bridge Oefenen

Oefen samen met een partner het bieden (5-kaart hoog) op je Android-telefoon,
tegen computertegenstanders op Oost en West.

De app is een web-app: de server draait op een pc en de telefoons openen hem
in Chrome. Via het menu "Toevoegen aan startscherm" krijg je een eigen
app-icoon.

## Stand van zaken

1. **Gedeelde tafel met biedkast** – klaar. Noord maakt een tafel aan, Zuid doet
   mee met de code van 4 letters. Oost en West passen voorlopig altijd.
2. AI-tegenstanders (BEN) – volgt.
3. Nabespreking per spel – volgt.
4. Server op je eigen pc, met een tunnel voor je partner – volgt.

## Starten op Windows

1. Installeer [Python 3.12 of nieuwer](https://www.python.org/downloads/windows/)
   (vink "Add python.exe to PATH" aan).
2. Open PowerShell in deze map en voer eenmalig uit:

   ```powershell
   py -m venv .venv
   .venv\Scripts\pip install -r server\requirements.txt
   ```

3. Start de server:

   ```powershell
   .venv\Scripts\python -m uvicorn main:app --app-dir server --host 0.0.0.0 --port 8000
   ```

4. Open op de pc <http://localhost:8000>, of op een telefoon in hetzelfde wifi-netwerk
   `http://<ip-adres-van-je-pc>:8000` (het ip-adres vind je met `ipconfig`).
   Windows vraagt de eerste keer of Python door de firewall mag: kies "Privénetwerken".

## Tests

```powershell
.venv\Scripts\pip install -r server\requirements-dev.txt
cd server
..\.venv\Scripts\python -m pytest
```
