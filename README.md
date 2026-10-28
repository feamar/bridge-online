# Bridge Oefenen

Oefen samen met je partner het bieden (5-kaart hoog) op jullie Android-telefoons,
tegen sterke computertegenstanders op Oost en West.

- **Samen aan één tafel.** Noord maakt een tafel aan, Zuid doet mee met de code van
  4 letters of via de deellink. Jullie bieden live met een biedkast.
- **Sterke tegenstanders.** Oost en West bieden met [BEN](https://github.com/lorserker/ben),
  een open-source bridge-engine op basis van neurale netwerken. BEN speelt SAYC, het
  standaard 5-kaart-hoogsysteem. Tik op een bod van de tegenstanders om te zien wat het betekent.
- **Nabespreking na elk spel.** Je ziet alle vier de handen, hoeveel slagen elk contract
  bij open kaart oplevert, het par-contract met de score, en wat BEN in jullie plaats
  had geboden, met uitleg.

De app is een web-app: alles draait op je eigen pc en de telefoons openen hem in
Chrome. Via het menu ⋮ → **Toevoegen aan startscherm** krijg je een eigen app-icoon.

## Eenmalig installeren op Windows

1. **Python 3.13** installeren via <https://www.python.org/downloads/windows/>.
   Vink tijdens de installatie **Add python.exe to PATH** aan.
2. **BEN** downloaden: ga naar <https://github.com/lorserker/ben/releases>, open de
   nieuwste versie en download het zip-bestand dat met **BENAPI** begint. Pak het uit
   naar `C:\BEN`, zodat `gameapi.exe` in die map (of een submap) staat.
   Windows kan waarschuwen dat het programma onbekend is; kies dan "Meer info" →
   "Toch uitvoeren".
3. **Deze code** downloaden: op GitHub → **Code** → **Download ZIP**, en uitpakken
   naar bijvoorbeeld `C:\bridge-online`.

## Spelen

1. Dubbelklik in de map `bridge-online` op **Start Bridge.cmd**.
   De eerste keer installeert het script de benodigde pakketten en het
   Cloudflare-tunnelprogramma; dat duurt een paar minuten. Daarna start het BEN
   (ongeveer een minuut), de tunnel en de server.
2. Het venster toont een adres zoals `https://iets-willekeurigs.trycloudflare.com`.
   Het staat ook op je klembord. Open dat adres op je telefoon en maak een tafel aan.
3. Tik bovenaan op **Tafel ABCD** om de uitnodiging naar Tobias te sturen.
4. Klaar? Sluit het venster; dan stoppen BEN, de tunnel en de server.

Het adres is bij elke start anders. Tafels bestaan alleen zolang de server draait.

### Instellingen

`windows\start.ps1` zoekt `gameapi.exe` in `C:\BEN`, `C:\BENAPI`, een map `ben`
in deze map en een map `BENAPI` naast deze map. Staat BEN ergens anders, zet dan
de omgevingsvariabele `BEN_DIR` op die map.

De server kent verder deze omgevingsvariabelen:

| Variabele    | Betekenis                                              | Standaard               |
|--------------|--------------------------------------------------------|-------------------------|
| `BRIDGE_AI`  | `ben`, of `pass` voor tegenstanders die altijd passen  | `ben`                   |
| `BEN_URL`    | adres van BEN                                          | `http://127.0.0.1:8085` |
| `BEN_SYSTEM` | biedsysteem van BEN (`SAYC`, `21GF` of `21GF-GIB`)     | `SAYC`                  |
| `PUBLIC_URL` | adres voor uitnodigingslinks (zet het startscript zelf)| leeg                    |

Is BEN niet bereikbaar, dan passen de tegenstanders en meldt de app dat.

## Zonder startscript

```powershell
py -3.13 -m venv .venv
.venv\Scripts\pip install -r server\requirements.txt
.venv\Scripts\python -m uvicorn main:app --app-dir server --host 0.0.0.0 --port 8000
```

Open dan <http://localhost:8000>, of op een telefoon in hetzelfde wifi-netwerk
`http://<ip-adres-van-je-pc>:8000`.

## Tests

```powershell
.venv\Scripts\pip install -r server\requirements-dev.txt
cd server
..\.venv\Scripts\python -m pytest
```
