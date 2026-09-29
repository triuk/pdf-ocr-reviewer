# Uživatelská zkouška ergonomie

Připraveno 2026-09-29 po etapách 1–5. Následující vývoj čeká na zpětnou vazbu
z této zkoušky. Výkonová etapa 6 ani nové vydání zatím nejsou zahájené.

## Spuštění připravené Linuxové verze

Z kořene projektu spusťte:

```bash
./dist/spustit-test-ergonomie.sh
```

Spouštěč používá `dist/pdf-ocr-reviewer-ergonomie`, složku
`dist/ergonomie-demo` a samostatné lokální koncepty v `dist/ergonomie-state`.
Tři PDF jsou zkušební kopie. Barevné stavy oprav jsou simulované pro test
ovládání; nejsou dokladem provedené opravy OCR. Původní PDF se nemění.

## Co vyzkoušet

1. **Označení bez zbytečných kliků:** v prvním PDF stiskněte M, vyberte
   „Špatná velikost boxu“, klikněte na slovo a tažením označte oblast.
   Přidejte poznámku; jedno označení zrušte křížkem přímo na boxu.
   Typ další připomínky má zůstat zapamatovaný.
2. **Navigace a filtry:** použijte „Má otevřené připomínky“ a filtr názvu
   souboru. Šipky nahoru/dolů mají zůstat mezi odpovídajícími PDF.
   Pro další zkoušku filtr názvu vymažte a stav souboru nastavte na všechny.
3. **Ověřování napříč PDF:** spusťte „Ověřit opravy · V“ a potvrzujte klávesou
   C. V čerstvé ukázce jsou celkem čtyři opravy k ověření. Aplikace má sama
   přejít mezi soubory a po poslední opravě zobrazit dokončení.
4. **Vrácení připomínky:** u právě potvrzeného místa stiskněte R. Má se znovu
   objevit jako otevřené. Obsah PDF zůstává stejný. Zkontrolujte také J/K
   pro přechod mezi připomínkami a N pro jejich poznámku.
5. **Návrat k práci:** zavřete aplikaci, spusťte ji znovu a zkontrolujte stavy
   a poznámky. Zrušené označení lze najít ve filtru „Zrušené“ a obnovit.

Stačí zpětná vazba, ve kterém kroku bylo nutné hledat ovládání, zbytečně klikat,
vracet fokus nebo opravovat nečekaný přechod. U chyby pomůže název PDF,
poslední akce a očekávaný výsledek. Technické testy konfliktů a restartu
nejsou součástí této ruční zkoušky; proběhly automaticky.

## Opakovatelnost a ověření

Zdroj testovací sady lze vytvořit do nové složky:

```bash
python tools/create_ergonomics_demo.py /nova/testovaci/slozka --source /cesta/ke/kopirovanemu.pdf
```

Bez `--source` vzniknou syntetické PDF. Existující testovací složku nástroj
nepřepisuje. Pro běh ze zdrojů použijte `python main.py --folder /nova/testovaci/slozka`.

Ověřeno lokálně na Linuxu: 66 Python testů, 11 JS scénářů, zdrojový i zabalený self-test,
CLI binárky pro zápis se správnou i zastaralou revizí
a skutečný WebUI/Chromium průchod označením, autosave, konfliktem, restartem,
obnovou poznámky, výběrem zálohy a potvrzováním přes dvě PDF. Testovací job CI
nově obsahuje Python i JS testy na Linuxu a Windows; Windows běh ještě nebyl
v této práci proveden. Kompletní CI, výkon a veřejné vydání patří do dalších etap.
