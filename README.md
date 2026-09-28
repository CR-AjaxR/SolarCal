# ☀️ Solar Savings — Home Assistant Integration

Track the money your solar panels are saving you in real time. Watch your setup cost tick down live as your panels generate power.

## Features

- **Live payback countdown** — your solar setup cost ticks down in real time as panels generate
- **Live "Saved Today"** counter — updates every 100ms based on current solar output
- **Daily & monthly savings** in £ (or your currency)
- **Lifetime savings tracker** — persists across HA restarts, accumulates day by day
- **Progress bar** — see how much of your setup cost has been paid off
- **Live solar power display** — current Watts and kW input
- **Beautiful dark Lovelace card** with glowing solar theme

---

## Installation

### Step 1 — Install the Integration

#### Option A: HACS Custom Repository (recommended)

1. In Home Assistant, go to **HACS → Integrations**
2. Click the **⋮ menu** → **Custom repositories**
3. Add your repository URL, category: **Integration**
4. Search for **Solar Savings** and install

#### Option B: Manual

1. Download this repository as a ZIP
2. Extract the `custom_components/solar_savings/` folder
3. Copy it to your HA config directory: `/config/custom_components/solar_savings/`
4. Restart Home Assistant

---

### Step 2 — Install the Lovelace Card

1. Copy `www/solar-savings-card/solar-savings-card.js` to your HA config:
   `/config/www/solar-savings-card/solar-savings-card.js`

2. In Home Assistant, go to **Settings → Dashboards → Resources**
3. Click **Add Resource**
4. URL: `/local/solar-savings-card/solar-savings-card.js`
5. Resource type: **JavaScript module**
6. Click **Create**

---

### Step 3 — Configure the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Solar Savings**
3. Fill in the form:

| Field | Description | Example |
|-------|-------------|---------|
| Live Solar Power Sensor | Your sensor reporting current Watts | `sensor.solar_power` |
| Daily Solar Energy | kWh produced today | `sensor.solar_energy_today` |
| Monthly Solar Energy | kWh produced this month | `sensor.solar_energy_month` |
| Electricity Rate | Cost per kWh | `0.33` |
| Setup Cost | Total cost to pay off | `5000` |
| Currency Symbol | Your currency | `£` |

> **Tip:** Your sensors can report in Wh or kWh — the integration auto-converts.

---

### Step 4 — Add the Card to Your Dashboard

1. Edit your Lovelace dashboard
2. Add a **Manual card**
3. Paste:

```yaml
type: custom:solar-savings-card
title: Solar Savings
```

That's it! The card automatically reads from your Solar Savings sensors.

---

## Sensors Created

After setup, these sensors appear in Home Assistant:

| Sensor | Description |
|--------|-------------|
| `sensor.solar_savings_current_savings_rate` | Current earning rate (£/hr) based on live watts |
| `sensor.solar_savings_savings_today` | Money saved today (£) |
| `sensor.solar_savings_savings_this_month` | Money saved this month (£) |
| `sensor.solar_savings_total_lifetime_savings` | Total accumulated savings since tracking began (£) |
| `sensor.solar_savings_payback_remaining` | Remaining setup cost to pay off (£) |

All sensors update in real time whenever your source sensors change.

---

## How the Payback Tracker Works

- Each day, the integration tracks the highest daily kWh reading seen
- At midnight (or when HA restarts after a day change), that value is added to the lifetime total
- The lifetime total × your rate = lifetime savings
- Remaining = Setup Cost − Lifetime Savings
- The Lovelace card then **ticks this down live** at the current solar earning rate (updates every 100ms)

---

## Updating Settings

To change your electricity rate, setup cost, or sensors:

1. Go to **Settings → Devices & Services**
2. Find **Solar Savings** → click **Configure**
3. Update any value and save

---

## Troubleshooting

**Sensors show "unavailable"** — Check your source sensor entity IDs are correct in the integration settings.

**Card shows dashes (—)** — Make sure the Lovelace resource is registered and the integration sensors exist.

**Lifetime total not accumulating** — The accumulation happens when a new day is detected. Leave HA running overnight and it will pick up automatically.

**Card not found** — Make sure the JS file is in the correct path (`/config/www/solar-savings-card/solar-savings-card.js`) and the resource is registered.

---

## Example Dashboard Setup

```yaml
views:
  - title: Solar
    cards:
      - type: custom:solar-savings-card
        title: "My Solar Savings"
      - type: entities
        title: Solar Sensors
        entities:
          - sensor.solar_savings_current_savings_rate
          - sensor.solar_savings_savings_today
          - sensor.solar_savings_savings_this_month
          - sensor.solar_savings_total_lifetime_savings
          - sensor.solar_savings_payback_remaining
```
