# PoolLab Local

Lokale Bluetooth-integratie voor de **PoolLab 1.0** watertester in Home
Assistant, via de officiële BLE-API — volledig zonder cloud.

> **Fork.** Dit is een fork van
> [mf76130/ha-poollab-local](https://github.com/mf76130/ha-poollab-local)
> (v0.4.1) met bugfixes, een meettijdstip, offline parsertests en een
> Nederlandse interface. Zie [CHANGELOG.md](CHANGELOG.md) voor de verschillen.

## Waarom lokaal

De bekende PoolLab-integraties voor Home Assistant
([dala318/python_poollab](https://github.com/dala318/python_poollab),
[stefanh12/Poollab](https://github.com/stefanh12/Poollab)) halen hun gegevens
op bij `labcom.cloud`. Dat betekent dat je eerst met de LabCOM-app naar de
cloud moet synchroniseren voordat Home Assistant iets ziet.

Deze integratie praat rechtstreeks met het apparaat over Bluetooth LE. De
fabrikant publiceert het protocol zelf
([BLE.pdf](https://poollab.org/static/api/BLE.pdf), Water-i.d. GmbH, versie 2),
dus er komt geen reverse-engineering aan te pas — en er gaat geen meetgegeven
het huis uit.

## Functies

- Automatische herkenning van de PoolLab 1.0 via de Bluetooth-integratie van
  Home Assistant (match op service-UUID), inclusief ESPHome Bluetooth-proxy's
- Leest op afroep alle opgeslagen metingen uit het flashgeheugen
  (`GET_INFO` + `GET_MEASURES`)
- Maakt per aangetroffen meetparameter automatisch een sensor aan (pH, vrij
  chloor, broom, alkaliniteit, …); per parameter telt de nieuwste meting
- Attribuut `measured_at` per sensor plus een aparte sensor **"Laatste meting"**
- Batterijsensor
- Knop **"Nu ophalen"** om direct na een meting uit te lezen
- Waarden overleven een herstart van Home Assistant (`RestoreEntity`)

## Vereisten

- Home Assistant met de Bluetooth-integratie actief
- Bluetooth-ontvangst binnen bereik van het apparaat: een adapter in de
  HA-host, of een ESPHome Bluetooth-proxy met **`bluetooth_proxy: active: true`**
  (actieve verbindingen zijn vereist — passief meeluisteren volstaat niet,
  omdat het protocol een commando/antwoord-uitwisseling is)

## Installatie via HACS

1. HACS → drie puntjes rechtsboven → **Custom repositories**
2. Repository: `https://github.com/mhoogenbosch/ha-poollab-local`, categorie
   **Integration**
3. Zoek "PoolLab Local", installeer, herstart Home Assistant
4. **Instellingen → Apparaten en diensten**: staat de PoolLab aan en binnen
   bereik, dan verschijnt hij als ontdekt apparaat. Anders via "Integratie
   toevoegen" → "PoolLab Local"

## Gebruik

De PoolLab schakelt zichzelf standaard na ongeveer 300 seconden uit, en
accepteert maar één BLE-verbinding tegelijk. Het werkt daarom zo:

1. Doe je meting op het apparaat zoals gebruikelijk
2. Druk binnen dat tijdvenster op **"Nu ophalen"** in Home Assistant
3. De sensoren worden bijgewerkt met de nieuwste meting per parameter

Er is bewust **geen** achtergrond-polling: dat zou alleen maar Bluetooth-verkeer
opleveren voor een apparaat dat een paar keer per week aanstaat, en botsen met
de LabCOM-app. Wil je het toch, zet dan `UPDATE_INTERVAL_SECONDS` in
`const.py` op een aantal seconden.

### Streefwaarden

`IDEAL_RANGES` in `const.py` bepaalt de attributen `ideal_low`, `ideal_high` en
`ideal_range_status` (`te laag` / `ok` / `te hoog`). De standaardwaarden zijn
gangbare richtwaarden voor een privé-buitenbad met chloor — pas ze aan op je
eigen situatie. Ze horen niet bij het BLE-protocol.

## Tests

```bash
python3 tests/test_parsers.py
```

Valideert de frame-parsers tegen synthetische protocolframes, zonder hardware
en zonder HA-runtime.

## Beperkingen

- Alleen lezen. Schrijfcommando's (contrast, ppm/mg-L omschakelen, geheugen
  wissen, klok zetten) zijn in `const.py` gedefinieerd maar niet als service
  of entiteit ontsloten.
- Tijdens het uitlezen kan de LabCOM-app niet gelijktijdig verbinden.
- De integratie is gebouwd op de officiële protocoldocumentatie. Werkt er iets
  niet, zet dan `custom_components.poollab_local: debug` onder `logger.logs`.

## Licentie

Zie [LICENSE](LICENSE). Met dank aan
[mf76130](https://github.com/mf76130/ha-poollab-local) voor het oorspronkelijke
werk en aan [kenavn](https://github.com/kenavn/esphome-poollab) voor de
leesbare protocoltranscriptie.
