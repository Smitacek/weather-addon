# Předpověď výroby FV a sběr časových řad

Datum: 11. 10. 2026. Stav: návrh k uživatelské kontrole, implementace nezačala.
Výchozí originál: Smitacek/weather-addon, commit 9e6c1c4.

## Cíl a rozhodnutí

Rozšíříme existující Weather a Weather Dashboard. Weather bude vlastníkem
výpočtu a trvalého archivu, Dashboard zobrazí jeho výsledky přes MQTT.
Nevytváříme další doplněk ani druhý proces komunikující po sériové lince.

První verze odpoví: jaký výkon a energii mohou dodat obě FV plochy během
následujících 72 hodin, zvlášť zítra a pozítří, a jak se předchozí odhady
shodují s měřením. Uloží dostatek kontextu pro pozdější kalibraci podle
počasí, denní a roční doby. Nebude ještě ovládat měnič ani počítat závazný
cíl nabíjení baterie. Kalibrační koeficienty se zatím nebudou měnit automaticky.

Samostatná nová aplikace by duplikovala příjem počasí, MQTT a konfiguraci.
Pouhé přenastavení Forecast.Solar neposkytne požadovaný vlastní archiv
vydání předpovědí a kontext omezení výroby. Může zůstat srovnávacím zdrojem.

## Instalace a předpoklady

- Dvě pole po 7 × 500 Wp: 3,5 kWp JJZ a 3,5 kWp JV, celkem 7 kWp.
- Výchozí návrhové azimuty od severu: 202,5° a 135°.
- Montáž na stěnách. Pro první odhad použijeme sklon 90° jako explicitně
  nepotvrzený předpoklad, který Dashboard zobrazí. Sklon, azimut, ztráty
  a koeficient teploty budou nastavitelné pro každé pole.
- Umístění převezmeme z existujících options bez zveřejnění souřadnic.
- Přiřazení fyzických polí k FV1/FV2 není potvrzené. Celkovou výrobu lze
  porovnávat ihned, kalibrace jednotlivých polí zůstane zablokovaná do
  potvrzení mapování. Neodvodíme mapování z jednoho naměřeného okamžiku.
- Výchozí konstantní systémová ztráta 14 % je modelový předpoklad,
  nikoli změřená účinnost. Pro neznámé lokální stínění zatím faktor 1.
- Europe/Prague je místní kalendář; archiv používá UTC.

## Model a oddělení veličin

Zachováme Open-Meteo. Vyžádáme hodinové globální záření na nakloněné ploše
pro každou geometrii, s normalizovanými jednotkami SI. Pro tento provider
se azimut převádí na jih = 0°, tedy +22,5° a −45°.
První verze nepřidává těžkou závislost na numpy/scipy/pvlib do Alpine image;
implementuje přímo jednoduchou dokumentovanou rovnici PVWatts pro DC výkon:

`P_dc = capacity_W × POA_W_m2 / 1000 × (1 + gamma_per_C × (T_cell_C − 25)) × loss_factor`.

Teplotu článku odhadneme aproximací NOCT:
`T_cell = T_air + (NOCT − 20) × POA / 800`.
Tato aproximace nezohledňuje plně větrání fasády; parametry a verze modelu
budou uloženy u každého vydání. Výkon je nezáporný, ale neomezuje se
automaticky jmenovitým DC výkonem ani nepotvrzeným AC limitem měniče.

Výsledek je **odhad dostupného DC výkonu a energie**, nikoli záruka skutečně
odebrané energie nebo AC dodávky. Naměřené FV1/FV2 a AC výstup zobrazíme
samostatně. AC využití, účinnost měniče a nabíjení nejsou součástí první predikce.
Doplňkový konzervativní scénář je nastavitelný násobek 0,8 základního odhadu;
nenazývá se statistickým kvantilem ani pravděpodobností.

## Čas a úplnost

Hodinové záření Open-Meteo reprezentuje předchozí hodinu. Každý interval
proto má `interval_start_utc`, `interval_end_utc` a průměrný výkon.
Energie se počítá z reálného trvání intervalu. Zbytek aktuální hodiny je
proporcionální aproximace, ve výstupu označená jako částečný interval.

Provider načte dostatečné pokrytí včetně hodin za koncem posledního
místního dne. Denní agregace provede průnik intervalů s místním kalendářem,
včetně 23/25hodinových dnů. Oddělíme dnešní zbývající energii od celodenního
odhadu; předpovězená ranní energie není skutečné měření.
Neúplný zítřek/pozítří nebude prezentován jako úplný denní součet.
Chybějící záření znamená neplatný interval, nikoli nulovou výrobu.

## Archiv vydání předpovědi

Přidáme SQLite archiv v `/data/solar.sqlite3` s verzovaným schématem,
transakcemi a omezenou retencí. Každé úspěšné vydání uloží:

- jedinečné ID, čas získání dat a čas vytvoření předpovědi;
- případný skutečný čas běhu meteorologického modelu, jen pokud ho provider poskytne;
- konfiguraci polí, model, datovou verzi a kvalitu vstupů;
- všechny cílové intervaly, počasí, geometrii, výkon a energii obou polí;
- úplnost místních dní a použitou rezervu konzervativního scénáře.

Čas HTTP stažení se nesmí označit jako čas meteorologického modelu.
Chyby síťového požadavku nevytvářejí nová platná vydání ze starých dat.
Výchozí retence pro nový archiv bude 400 dní, samostatná od existujících
JSONL logů s 90denní retencí. Denní úklid maže záznamy podle jejich časů.
Chyba zápisu se viditelně ohlásí, předpověď může pokračovat s příznakem
nefunkčního archivu; výsledky nesmějí tvrdit, že sběr historie funguje.

## Skutečnost a omezená výroba

Weather přidá pouze čtení nakonfigurovaných MQTT telemetrických témat.
Z EASUN čte výkon, napětí a proud FV1/FV2, AC výstup a dostupný provozní režim; z BMS SoC a výkon
obou baterií. Při nasazení ověříme konkrétní témata a dostupnost proti běžící
instalaci. Nezavádíme serial přístup ani HA administrátorský token.

Každá minuta uloží hodnoty, časy přijetí, stáří a příznaky dostupnosti.
Retained telemetrie po startu se bez ověřeného zdrojového času nepovažuje
za čerstvé měření. Publikační kadence BMS/EASUN slouží pro limity stáří;
delší výpadek MQTT přeruší integraci, nedopočítáváme energii přes mezeru.
Hodinové skutečné energie vzniknou časovou integrací platných úseků
a obsahují procento pokrytí. Jsou určeny pro vyhodnocení, nepřidávají další
zdroj měření do HA Energy vedle již existujících čítačů.

Kvalita intervalu je `missing`, `ambiguous`, `suspected_curtailed`,
`confirmed_curtailed` nebo `eligible`. Příznaky nesou důvody.
Nízká zátěž sama nestačí pro omezení; vysoké SoC spolu s minimálním nabíjením
může být podezření. Potvrzení vyžaduje explicitní režim/limit z měniče.
Pokud chybí důkaz volné nabíjecí kapacity nebo relevantní limity, interval
zůstává nejednoznačný. Rozdíl proti předpovědi není sám důkaz omezení.
Omezené vzorky zůstávají v archivu, ale nevstupují do kalibračního souboru.
První verze bez dostatečných důkazů může mít málo způsobilých vzorků.

Napětí FV1/FV2 uložíme jako další časové řady včetně proudů a původního
reportovaného výkonu. Než se U × I použije jako kontrola, ověříme význam
proudových polí konkrétního protokolu; proud může být referovaný na jinou
stranu regulátoru. Vyšší napětí při nízkém výkonu může ukazovat provoz
blíže napětí naprázdno a omezení odběru, ale bez dalšího kontextu nejde
o potvrzení omezení. Z jediné hodnoty napětí nelze rekonstruovat maximum
I–V křivky. Potenciální výkon odhadne model počasí a kalibrace z nezastropovaných
intervalů; napětí zlepší diagnostiku a výběr vzorků. Detailní elektrický
model později vyžaduje typ panelů, Voc/Vmp/Isc/Imp a zapojení stringů.

Vyhodnocení použije vydání skutečně existující před začátkem hodnoceného
intervalu, s uvedeným předstihem. Pozdější aktualizace nesmí nahradit
původní odhad při hodnocení jeho přesnosti. Zobrazíme chybu a počet úplných
a způsobilých hodin; sezónní přesnost se neslibuje po několika dnech.

## HA a Dashboard

Přidáme nový verzovaný MQTT kontrakt pod `<prefix>/<site_id>/solar/`.
Retained profil obsahuje ID vydání a intervaly na 72 hodin; denní metriky
obsahují místní datum, pokrytí a platnost. Staré unique_id zůstávají stabilní.
Opravený význam DNI a denních GHI výslovně zdokumentujeme datovou verzí 2;
archiv nepovažuje původní DNI za správně změřenou veličinu.

Nové HA senzory: odhad dostupného FV výkonu (W, power, measurement), odhad
energie zítra/pozítří a zbývající dnes (kWh, energy, bez state_class),
konzervativní denní energie, čas poslední platné předpovědi (timestamp)
a diagnostika platnosti/archivu. Předpovězená energie nemá total_increasing
a nezapojí se jako naměřená výroba do Energy.

Forecast dostupnost je oddělená od MQTT LWT. Nejpozději po třech cyklech
bez úspěšného získání dat bude forecast nedostupný; timestamp a Dashboard
umožní rozpoznat stará retained data i po restartu. Discovery dostane
odpovídající expire_after; HA birth vyvolá obnovení discovery.

Rozšíříme skutečně obsluhovaný Dashboard, nikoli nepřipojené JS funkce.
Ukáže dvě pole, součet, 72hodinový průběh, zítřek/pozítří, pozorované FV,
stáří a nepotvrzené parametry. Nové API `/api/solar` obslouží tento profil;
Weather přes MQTT publikuje také omezený souhrn posledních hodnocení.
Bez dat obrazovka zobrazí nedostupnost, ne nuly ani ilustrační graf.

## Migrace, ověření a nasazení

Zachováme slugy a existující instalace, přidáme zpětně kompatibilní options
pro více polí a sběr telemetrie. Bez nové konfigurace PV zůstane PV model
vypnutý a původní počasí dostupné. Validace neznámých providerů/modelů či
nepodporovaných jednotek má skončit srozumitelnou chybou, nikoli tichým
výpočtem s nesprávnými jednotkami.

Plánované verze jsou Weather 0.2.0 a Weather Dashboard 0.2.0. Před vydáním
musí projít testy fyzikálních jednotek a geometrie, nulového/nočního záření,
dvou polí, částečných intervalů, půlnoci a obou změn času Europe/Prague;
dále chybějících hodnot, API selhání, stale/retained MQTT, restartu archivu,
retence, časové integrace přes výpadek a výběru předem vydané předpovědi.
Testy využijí deterministické fixtures, ne závislost na živém počasí.

Při nasazení zazálohujeme stávající options a data doplňků. Ověříme sestavení
na architektuře HA, MQTT identity, novou předpověď, přírůstek skutečných
vzorků, přežití restartu a funkční Dashboard. Záznamy a mapu aktualizujeme
až podle skutečně ověřeného výsledku. Návrat spočívá v předchozí verzi
a options; nový archiv se uchová odděleně. Automatické řízení nabíjení,
tarify a rezerva baterie zůstávají samostatným následujícím milníkem.

## Podklady

- https://open-meteo.com/en/docs
- https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html
- https://www.home-assistant.io/integrations/sensor/
- HA_MAP.md v pracovním adresáři house: ověřený průzkum 11. 10. 2026.
