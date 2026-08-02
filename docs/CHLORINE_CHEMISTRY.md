# Chlorine chemistry — reading your PoolLab sensors

Your PoolLab measures chlorine in two ways, and the difference between them is what
actually tells you whether the water is healthy. This page explains what the numbers mean
and how this integration handles them.

> Credit where due: the idea of documenting this alongside the integration, and of deriving
> combined chlorine as a sensor, comes from
> [stefanh12/Poollab](https://github.com/stefanh12/Poollab/blob/main/CHLORINE_CHEMISTRY.md)
> (MIT). This text is written for *this* integration and its local measurements.

---

## The three numbers

| | What it is | Target |
|---|---|---|
| **Free chlorine** | Chlorine still available to disinfect | **1–3 ppm** |
| **Total chlorine** | Everything present: free plus already spent | close to free chlorine |
| **Combined chlorine** | Chlorine already used up on contaminants | **below 0.5 ppm** |

**Free chlorine** is the working stock. It is the number that decides whether your pool is
safe to swim in right now.

**Total chlorine** is measured straight after free chlorine, in the same cuvette: the DPD 3
tablet is added to the sample that already holds the dissolved DPD 1. It counts free
chlorine plus everything that has already reacted.

**Combined chlorine** is the difference, and it is the interesting one. This is chlorine
that has bound to sweat, sunscreen, urine and other organics, forming chloramines. Those
no longer disinfect — but they *do* cause the sharp "chlorine smell", stinging eyes and
irritated skin. A pool that reeks of chlorine usually does not have too much chlorine; it
has too much *combined* chlorine and too little free chlorine.

This integration derives it as `sensor.poollab_combined_chlorine`.

---

## Reading the combination

| Free | Combined | What it means |
|---|---|---|
| 1–3 ppm | < 0.5 ppm | Healthy. Nearly all chlorine is still active. |
| 1–3 ppm | > 0.5 ppm | Chloramines building up. Shock the pool to break them down. |
| < 1 ppm | any | Too little disinfectant. Add chlorine. |
| < 1 ppm | > 0.5 ppm | Both problems at once: add chlorine *and* shock. |

Combined chlorine higher than free chlorine means the pool needs attention promptly — most
of the chlorine present is spent, and little is doing any work.

---

## When the sensor deliberately shows nothing

Subtracting two numbers that do not belong together produces a plausible-looking figure
that is simply wrong, so the sensor stays empty unless the subtraction is meaningful. It
reports `reason_unavailable` when it declines. That happens when:

- **Only one of the two has been measured.** Free chlorine alone says nothing about
  chloramines.
- **The readings are more than 15 minutes apart.** Total chlorine is meant to be measured
  seconds after free chlorine in the same cuvette. Pairing this morning's free chlorine
  with last week's total is meaningless.
- **Either reading is out of range.** An overrange value is clamped to the top of the
  measuring range — a lower bound, not a measurement. Subtracting it would present a guess
  as fact.

If free chlorine comes out slightly above total chlorine (measurement noise at low
concentrations), the result is reported as `0.0`, not as a negative amount.

---

## How chlorine relates to the rest of the water

Chlorine does not act in isolation, which is why a low reading is not always a chlorine
problem:

- **pH decides how well chlorine works.** Around pH 7.0–7.4 a large share of free chlorine
  is present as hypochlorous acid, the form that actually disinfects. At pH 7.9 that share
  drops sharply — the same measured value does noticeably less work. Correct pH first, then
  judge chlorine.
- **Cyanuric acid protects chlorine from sunlight.** Without stabiliser (target 30–50 ppm)
  UV destroys free chlorine within hours, so an outdoor pool keeps testing low no matter
  how much you add. Too much has the opposite effect and blunts the chlorine.
- **Alkalinity keeps pH stable.** Too low and pH swings on every addition; too high and pH
  creeps up persistently and resists correction.

So a reading of "free chlorine 0.2 ppm" can mean too little chlorine added, or no
stabiliser, or a pH that renders the chlorine ineffective. Measure the set, not one value.

---

## Example automations

Alert when the pool needs shocking:

```yaml
automation:
  - alias: "Pool - shock needed (chloramines)"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.poollab_combined_chlorine
        above: 0.5
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "Pool needs shocking"
          message: >
            Combined chlorine is
            {{ states('sensor.poollab_combined_chlorine') }} ppm
            (free: {{ state_attr('sensor.poollab_combined_chlorine', 'free_chlorine') }} ppm).
```

Alert on low free chlorine, ignoring failed measurements:

```yaml
automation:
  - alias: "Pool - free chlorine low"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.poollab_free_chlorine
        below: 1.0
    conditions:
      - condition: template
        value_template: >
          {{ state_attr('sensor.poollab_free_chlorine', 'status') == 'ok' }}
    actions:
      - action: notify.mobile_app_phone
        data:
          message: >
            Free chlorine is {{ states('sensor.poollab_free_chlorine') }} ppm.
            Target is 1-3 ppm.
```

The `status` check matters: a measurement taken without a reagent tablet reports
`under_range`, and without that condition every failed test would page you.

---

## Measuring order

Each parameter needs its own fresh 10 ml sample and its own ZERO, taken without reagent,
before the tablet goes in. **Total chlorine is the exception**: measure it directly after
free chlorine without emptying the cuvette.

Free chlorine must be read **within one minute** of the tablet dissolving — after that the
values drift upward and your combined chlorine comes out too low.

---

## References

- PoolLab 1.0 user manual, chlorine section (p. 32–36) — the DPD 1 / DPD 3 procedure and
  the combined = total − free derivation
- [CDC — disinfection and testing for residential pools](https://www.cdc.gov/healthywater/swimming/residential/disinfection-testing.html)
- WHO Guidelines for Safe Recreational Water Environments, volume 2

General guidance only; follow the recommendations for your own pool type and volume.
