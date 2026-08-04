# WebUI reference a uživatelské rozhraní

## 3. Referenční projekt WebUI

Návrh vychází z dodaného archivu `example-webui-python.zip`.

### Zjištěná referenční verze

- hlavní repozitář: commit `538123e061622a702709a1dd9c5a22cd32592dd3`;
- UI submodul: commit `72070fe146df89d3e0a6325a0475783bfda6d40d`;
- Python závislost v ukázce: `webui2`;
- frontend je oddělen ve složce `ui/`;
- backend používá jednu třídu `WebUIApp` a funkce navázané přes `window.bind()`.

### Prvky, které převezmeme

1. **Oddělení backendu a frontendu**
   - Python ve vlastní aplikační vrstvě;
   - `ui/index.html`, `ui/index.js` a ručně udržovaný `ui/index.css`;
   - SCSS ani krok sestavení CSS se nepoužije.

2. **WebUI lifecycle**
   - `set_root_folder()` pro frontend;
   - otevření přes `show("index.html")`;
   - čekání aplikace přes `webui.wait()`;
   - samostatný uživatelský nebo vývojový režim `--server` se nepoužije; interní lokální transport WebUI zůstává pouze implementačním detailem.

3. **Obousměrné volání**
   - frontend volá Python přes funkce zaregistrované pomocí `window.bind()`;
   - Python vrací malé odpovědi jako JSON řetězec;
   - větší binární data mohou být odesílána přes `send_raw()`.

4. **Synchronizace po připojení**
   - `webui.setEventCallback()`;
   - při události `CONNECTED` frontend zavolá `syncStateB()`;
   - obecná funkce aplikuje stav na HTML prvky podle jejich `id`;
   - ochranný příznak zabrání tomu, aby aplikace při obnově stavu vyvolala zpětně ovládací události.

5. **Použitelné principy ovládacích prvků**
   - přepínače typu switch;
   - jednoduchý slider;
   - CSS proměnné;
   - automatický světlý a tmavý režim přes `prefers-color-scheme`;
   - systémové písmo a rozhraní bez externího CDN.

   Vizuální styl aplikace se navrhne samostatně podle potřeb kontroly OCR. Z referenčního projektu se nepřebírá vzhled tlačítek ani celkový styl stránky.

6. **Zápis/export souboru**
   - referenční postup s `showSaveFilePicker()` a záložním stažením je použit pro export CSV.

### Prvky, které nepřevezmeme

- graf Chart.js;
- dvojitý noUiSlider;
- periodické generování testovacích dat;
- generický frontend jako Git submodul.

UI této aplikace bude příliš specifické, proto se referenční projekt použije jako výchozí vzor, nikoli jako dlouhodobě připojený submodul.

---
