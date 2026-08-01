<p align="center">
  <img src="images/banner.svg" alt="PoolLab Local — lokale Bluetooth-integratie voor Home Assistant" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/HACS-custom%20repository-41BDF5?style=flat-square" alt="HACS custom repository">
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5?style=flat-square" alt="Home Assistant 2024.6+">
  <img src="https://img.shields.io/badge/verbinding-100%25%20lokaal-16A34A?style=flat-square" alt="100% lokaal">
  <img src="https://img.shields.io/badge/apparaat-PoolLab%201.0-0EA5E9?style=flat-square" alt="PoolLab 1.0">
</p>

Leest de **PoolLab 1.0** watertester van Water-i.d. rechtstreeks uit over Bluetooth
LE en zet elke meetparameter als sensor in Home Assistant. Geen cloud, geen account,
geen app die eerst moet synchroniseren.

> [!NOTE]
> Fork van [mf76130/ha-poollab-local](https://github.com/mf76130/ha-poollab-local) v0.4.1,
> met bugfixes, een meettijdstip, kloksynchronisatie, offline parsertests en een
> Nederlandse interface. Zie [CHANGELOG.md](CHANGELOG.md) voor alle verschillen.

---

## Waarom lokaal?

De bekende PoolLab-integraties voor Home Assistant —
[dala318/python_poollab](https://github.com/dala318/python_poollab) en
[stefanh12/Poollab](https://github.com/stefanh12/Poollab) — halen hun gegevens op bij
`labcom.cloud`. Je moet dan eerst met de LabCOM-app naar de cloud synchroniseren
voordat Home Assistant iets ziet, en je meetgegevens verlaten je huis.

Deze integratie praat rechtstreeks met het apparaat. De fabrikant publiceert het
protocol zelf ([BLE.pdf](https://poollab.org/static/api/BLE.pdf), Water-i.d. GmbH,
versie 2), dus er komt geen reverse-engineering aan te pas.

| | Cloud-integraties | **PoolLab Local** |
|---|---|---|
| Verbinding | Internet → labcom.cloud | Bluetooth LE, rechtstreeks |
| Account nodig | Ja, met API-token | Nee |
| App-sync vooraf | Ja | Nee |
| Werkt zonder internet | Nee | Ja |
| Meetgegevens verlaten het huis | Ja | Nee |

---

## Vereisten

- Home Assistant **2024.6** of nieuwer, met de Bluetooth-integratie actief
- Bluetooth-ontvangst binnen bereik van het apparaat. Dat kan een adapter in de
  HA-host zijn, of een **ESPHome Bluetooth-proxy**. Die proxy moet actieve
  verbindingen toestaan:

  ```yaml
  esp32_ble_tracker:
    scan_parameters:
      active: true
  bluetooth_proxy:
    active: true      # verplicht — passief meeluisteren volstaat niet
  ```

  Het protocol is een commando/antwoord-uitwisseling, dus er moet een echte
  GATT-verbinding opgezet kunnen worden.

---

## Installatie

### Via HACS (aanbevolen)

1. HACS → drie puntjes rechtsboven → **Custom repositories**
2. Repository `https://github.com/mhoogenbosch/ha-poollab-local`, categorie **Integration**
3. Zoek **PoolLab Local**, klik **Download**
4. **Herstart Home Assistant** (verplicht voor nieuwe integraties)
5. Zet de PoolLab aan binnen bereik van een proxy → hij verschijnt vanzelf onder
   **Instellingen → Apparaten en diensten** als ontdekt apparaat. Bevestigen is genoeg;
   er is niets in te vullen.

Verschijnt hij niet vanzelf, kies dan **Integratie toevoegen → PoolLab Local** en
selecteer het apparaat uit de lijst.

### Handmatig

Kopieer `custom_components/poollab_local` naar de `custom_components`-map van je
Home Assistant-configuratie en herstart.

---

## Gebruik

De PoolLab schakelt zichzelf standaard na **ongeveer 300 seconden** uit en accepteert
maar **één BLE-verbinding tegelijk**. De werkwijze is daarom:

1. Doe je meting op het apparaat zoals gebruikelijk
2. Druk binnen dat tijdvenster in Home Assistant op **Nu ophalen**
3. Per gemeten parameter verschijnt een sensor met de nieuwste waarde

Er is bewust **geen achtergrond-polling**. Dat zou alleen maar Bluetooth-verkeer
opleveren voor een apparaat dat een paar keer per week aanstaat, en botsen met de
LabCOM-app. Wil je het toch, zet dan `UPDATE_INTERVAL_SECONDS` in `const.py` op een
aantal seconden.

### Entiteiten

| Entiteit | Type | Omschrijving |
|---|---|---|
| `button.poollab_nu_ophalen` | knop | Verbindt nu en haalt de opgeslagen metingen op |
| `button.poollab_klok_gelijkzetten` | knop | Zet de apparaatklok gelijk met Home Assistant |
| `sensor.poollab_batterij` | sensor | Batterijniveau in procenten (diagnostisch) |
| `sensor.poollab_laatste_meting` | sensor | Tijdstip van de meest recente meting |
| `sensor.poollab_<parameter>` | sensor | Eén per gemeten parameter (pH, vrij chloor, …) |

Meetsensoren worden pas aangemaakt zodra die parameter een keer gemeten is, en blijven
daarna bestaan. Waarden overleven een herstart van Home Assistant.

### Attributen per meetsensor

| Attribuut | Betekenis |
|---|---|
| `measured_at` | Wanneer de meting op het apparaat is gedaan |
| `status` | `ok`, `onder meetbereik` of `boven meetbereik`, zoals het apparaat het meldt |
| `measure_id` | Volgnummer van de meting op het apparaat |
| `ideal_low` / `ideal_high` | Je streefwaarden voor deze parameter |
| `ideal_range_status` | `te laag`, `ok` of `te hoog` |

> [!IMPORTANT]
> Meet je zonder reagenstablet, dan rapporteert het apparaat zelf `onder meetbereik`
> met waarde `0.0`. Dat is geen fout van de integratie — het staat zo in het
> meetrecord. Kijk dus naar het `status`-attribuut voordat je een waarde vertrouwt.

### Streefwaarden aanpassen

`IDEAL_RANGES` in `const.py` bepaalt de `ideal_*`-attributen. De standaardwaarden zijn
gangbare richtwaarden voor een privé-buitenbad met chloor:

```python
IDEAL_RANGES = {
    1:  (1.0, 3.0),      # Totaal chloor (ppm)
    6:  (2.0, 4.0),      # Broom (ppm)
    8:  (1.0, 3.0),      # Vrij chloor (ppm)
    9:  (7.0, 7.4),      # pH
    10: (80.0, 120.0),   # Totale alkaliniteit (ppm)
    11: (30.0, 50.0),    # Cyanuurzuur (ppm)
    35: (200.0, 400.0),  # Totale hardheid (ppm)
}
```

Deze horen niet bij het BLE-protocol; pas ze aan op je eigen bad (zoutwater, broom, spa).

### Automation-voorbeelden

Waarschuwing als de pH buiten je streefwaarden ligt, met de mislukte metingen eruit:

```yaml
automation:
  - alias: "Zwembad - pH buiten streefwaarden"
    triggers:
      - trigger: state
        entity_id: sensor.poollab_ph
    conditions:
      - condition: template
        value_template: "{{ state_attr('sensor.poollab_ph', 'status') == 'ok' }}"
      - condition: template
        value_template: >
          {{ state_attr('sensor.poollab_ph', 'ideal_range_status') != 'ok' }}
    actions:
      - action: notify.mobile_app_telefoon
        data:
          title: "Zwembad pH"
          message: >
            pH is {{ states('sensor.poollab_ph') }}
            ({{ state_attr('sensor.poollab_ph', 'ideal_range_status') }}).
```

Herinnering als er al een week niet gemeten is:

```yaml
automation:
  - alias: "Zwembad - al een week geen watertest"
    triggers:
      - trigger: template
        value_template: >
          {{ now() - states('sensor.poollab_laatste_meting') | as_datetime
             > timedelta(days=7) }}
    actions:
      - action: notify.mobile_app_telefoon
        data:
          message: "Al een week geen zwemwater getest."
```

---

## Problemen oplossen

Zet eerst uitgebreide logging aan:

```yaml
logger:
  logs:
    custom_components.poollab_local: debug
```

| Symptoom | Oorzaak en oplossing |
|---|---|
| `was not seen by any Bluetooth adapter/proxy` | Het apparaat staat uit of is buiten bereik. Zet het aan; het gaat na ~300 s vanzelf weer uit. |
| `Timed out talking to PoolLab` | De verbinding lukte, maar het apparaat antwoordde niet. Meestal bezet de **LabCOM-app** de enige BLE-verbinding, of het apparaat staat in een meetstand of menu. Sluit de app, ga terug naar het hoofdscherm en probeer opnieuw. |
| Geen meetsensoren, alleen batterij | Het apparaatgeheugen is leeg. Doe een meting en druk op **Nu ophalen**. |
| Waarde `0.0` bij pH | Kijk naar `status`: bij `onder meetbereik` was de meting zelf ongeldig (geen reagenstablet). |
| `measured_at` klopt niet | De apparaatklok is verlopen. Druk op **Klok gelijkzetten**. |

---

## Hoe het werkt

Het apparaat biedt een eigen GATT-service (`PoolLabSvc`,
`A7EE04A9-507B-4910-A528-B619D5501924`) met drie characteristics:

| Characteristic | UUID | Rol |
|---|---|---|
| `CommandMOSI` | `91BFA536-…` | commando schrijven (≤128 bytes) |
| `CommandMISO` | `2FF18B59-…` | antwoord lezen (altijd 250 bytes) |
| `MISO_Signal` | `C2296C06-…` | notificatie: "antwoord staat klaar" |

Eén uitwisseling verloopt zo: verbinden zonder pairing, notificaties inschakelen op
`MISO_Signal`, het commando schrijven naar `CommandMOSI` (preamble `0xAB` + 16-bits
commando-ID + parameters), wachten op de notificatie, en het antwoord lezen van
`CommandMISO`. Alle meerbyte-getallen zijn little-endian.

De integratie stuurt `GET_INFO` (batterij, aantal opgeslagen metingen, klok) en
vervolgens `GET_MEASURES` voor de flashcellen. Het geheugen bestaat uit 16 cellen van
16 metingen, per helft van 8 uit te lezen; elk record is 16 bytes met volgnummer,
parametertype, status, tijdstempel en een IEEE-754 float als waarde.

Alleen lezen plus `SET_TIME` zijn ontsloten. De overige schrijfcommando's (contrast,
ppm/mg-L omschakelen, geheugen wissen, herstarten, slaapstand) staan wel in `const.py`
maar zijn bewust niet als knop of service beschikbaar.

---

## Tests

```bash
python3 tests/test_parsers.py
```

Bouwt synthetische `GET_INFO`- en `GET_MEASURES`-frames byte voor byte volgens de
specificatie en controleert of de parser ze correct ontleedt, inclusief randgevallen
als een onzinnige apparaatklok en niet-eindige meetwaarden. Draait zonder hardware en
zonder Home Assistant.

---

## Licentie en dank

Zie [LICENSE](LICENSE). Met dank aan
[mf76130](https://github.com/mf76130/ha-poollab-local) voor het oorspronkelijke werk en
aan [kenavn](https://github.com/kenavn/esphome-poollab) voor de leesbare transcriptie
van de protocoldocumentatie.
