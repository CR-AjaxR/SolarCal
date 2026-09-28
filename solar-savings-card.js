/**
 * Solar Savings Card for Home Assistant
 * Shows a live ticking payback countdown, daily/monthly savings,
 * and a real-time power feed display.
 *
 * Install: copy to /config/www/solar-savings-card/solar-savings-card.js
 * Add resource in HA: /local/solar-savings-card/solar-savings-card.js (JavaScript module)
 *
 * Card config:
 *   type: custom:solar-savings-card
 *   title: "Solar Savings"          # optional
 *   rate_entity: sensor.solar_savings_rate          # optional override
 *   today_entity: sensor.solar_savings_today        # optional override
 *   month_entity: sensor.solar_savings_month        # optional override
 *   lifetime_entity: sensor.solar_savings_lifetime  # optional override
 *   remaining_entity: sensor.solar_payback_remaining # optional override
 */

class SolarSavingsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._ticker = null;
    this._liveRemaining = null;
    this._liveSavedToday = null;
    this._ratePerSecond = 0;
    this._lastUpdate = null;
    this._hass = null;
    this._config = {};
    this._rendered = false;
  }

  // ── Config ──────────────────────────────────────────────────────────────────

  setConfig(config) {
    this._config = {
      title: config.title || "Solar Savings",
      rate_entity: config.rate_entity || "sensor.solar_savings_rate",
      today_entity: config.today_entity || "sensor.solar_savings_today",
      month_entity: config.month_entity || "sensor.solar_savings_month",
      lifetime_entity: config.lifetime_entity || "sensor.solar_savings_lifetime",
      remaining_entity: config.remaining_entity || "sensor.solar_payback_remaining",
    };
  }

  // ── hass setter ─────────────────────────────────────────────────────────────

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._render();
      this._rendered = true;
      this._startTicker();
    }
    this._updateFromHass();
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  _getState(entityId) {
    if (!this._hass) return null;
    const s = this._hass.states[entityId];
    return s ? s : null;
  }

  _getFloat(entityId, fallback = 0) {
    const s = this._getState(entityId);
    if (!s || s.state === "unavailable" || s.state === "unknown") return fallback;
    const v = parseFloat(s.state);
    return isNaN(v) ? fallback : v;
  }

  _getAttr(entityId, attr, fallback = null) {
    const s = this._getState(entityId);
    return s ? (s.attributes[attr] ?? fallback) : fallback;
  }

  _fmt(n, decimals = 2) {
    if (n === null || isNaN(n)) return "—";
    return n.toFixed(decimals);
  }

  _currency() {
    return this._getAttr(this._config.rate_entity, "currency", "£");
  }

  // ── Update from live HA states ──────────────────────────────────────────────

  _updateFromHass() {
    const ratePerHour = this._getFloat(this._config.rate_entity, 0);
    this._ratePerSecond = ratePerHour / 3600;

    const remaining = this._getFloat(this._config.remaining_entity, null);
    const today = this._getFloat(this._config.today_entity, 0);

    // Seed the live counters from HA values (they tick from here)
    if (this._liveRemaining === null || this._needsResync()) {
      this._liveRemaining = remaining;
      this._liveSavedToday = today;
      this._lastUpdate = performance.now();
    }

    // Static stats
    const currency = this._currency();
    const setupCost = this._getAttr(this._config.rate_entity, "setup_cost", "?");
    const watts = this._getAttr(this._config.rate_entity, "current_watts", 0);
    const kw = this._getAttr(this._config.rate_entity, "current_kw", 0);
    const month = this._getFloat(this._config.month_entity, 0);
    const lifetime = this._getFloat(this._config.lifetime_entity, 0);
    const pct = this._getAttr(this._config.lifetime_entity, "payback_percent", 0);

    this._updateStats({
      currency, setupCost, watts, kw, month, lifetime, pct, ratePerHour
    });
  }

  _needsResync() {
    // Resync ticker with HA value every 30 s
    return this._lastUpdate && (performance.now() - this._lastUpdate) > 30000;
  }

  // ── Ticker ───────────────────────────────────────────────────────────────────

  _startTicker() {
    if (this._ticker) return;
    let lastTick = performance.now();

    this._ticker = setInterval(() => {
      const now = performance.now();
      const elapsed = (now - lastTick) / 1000; // seconds
      lastTick = now;

      if (this._ratePerSecond > 0) {
        if (this._liveRemaining !== null) {
          this._liveRemaining = Math.max(0, this._liveRemaining - this._ratePerSecond * elapsed);
        }
        if (this._liveSavedToday !== null) {
          this._liveSavedToday = this._liveSavedToday + this._ratePerSecond * elapsed;
        }
      }
      this._tickDisplay();
    }, 100); // update every 100 ms for smooth animation
  }

  disconnectedCallback() {
    if (this._ticker) {
      clearInterval(this._ticker);
      this._ticker = null;
    }
    this._rendered = false;
    this._liveRemaining = null;
    this._liveSavedToday = null;
  }

  // ── DOM Updates ─────────────────────────────────────────────────────────────

  _tickDisplay() {
    const root = this.shadowRoot;
    const currency = this._currency();

    const remEl = root.getElementById("live-remaining");
    const todayEl = root.getElementById("live-today");

    if (remEl && this._liveRemaining !== null) {
      remEl.textContent = `${currency}${this._fmt(this._liveRemaining, 2)}`;
    }
    if (todayEl && this._liveSavedToday !== null) {
      todayEl.textContent = `${currency}${this._fmt(this._liveSavedToday, 4)}`;
    }
  }

  _updateStats({ currency, setupCost, watts, kw, month, lifetime, pct, ratePerHour }) {
    const root = this.shadowRoot;
    if (!root) return;

    const set = (id, val) => {
      const el = root.getElementById(id);
      if (el) el.textContent = val;
    };

    set("stat-month", `${currency}${this._fmt(month, 2)}`);
    set("stat-lifetime", `${currency}${this._fmt(lifetime, 2)}`);
    set("stat-setup", setupCost !== "?" ? `${currency}${parseFloat(setupCost).toFixed(2)}` : "—");
    set("stat-rate", `${currency}${this._fmt(ratePerHour, 4)}/hr`);
    set("stat-watts", watts !== null ? `${Math.round(watts)} W` : "—");
    set("stat-kw", kw !== null ? `${parseFloat(kw).toFixed(3)} kW` : "—");
    set("pct-label", `${parseFloat(pct || 0).toFixed(1)}% paid off`);

    const bar = root.getElementById("payback-bar-fill");
    if (bar) {
      bar.style.width = `${Math.min(100, parseFloat(pct || 0))}%`;
    }

    // Status dot colour
    const dot = root.getElementById("status-dot");
    if (dot) {
      const isGenerating = parseFloat(watts || 0) > 10;
      dot.style.background = isGenerating ? "#4cff91" : "#888";
      dot.title = isGenerating ? "Solar generating" : "No solar input";
    }
  }

  // ── Render HTML ─────────────────────────────────────────────────────────────

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--primary-font-family, "Roboto", sans-serif);
        }

        .card {
          background: linear-gradient(145deg, #0d1b2a 0%, #1a2e44 60%, #0d1b2a 100%);
          border-radius: 16px;
          padding: 20px;
          color: #e0f0ff;
          box-shadow: 0 4px 24px rgba(0,0,0,0.5);
          overflow: hidden;
          position: relative;
        }

        /* Subtle solar ray background */
        .card::before {
          content: "";
          position: absolute;
          top: -60px; left: 50%;
          transform: translateX(-50%);
          width: 300px; height: 200px;
          background: radial-gradient(ellipse at center, rgba(255,200,50,0.07) 0%, transparent 70%);
          pointer-events: none;
        }

        .header {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 18px;
        }

        .header h2 {
          margin: 0;
          font-size: 1.1rem;
          font-weight: 600;
          color: #a8d8ff;
          flex: 1;
        }

        .status-dot {
          width: 10px; height: 10px;
          border-radius: 50%;
          background: #888;
          box-shadow: 0 0 8px currentColor;
          transition: background 0.5s;
          flex-shrink: 0;
        }

        /* ── Payback countdown ── */
        .countdown-section {
          text-align: center;
          margin-bottom: 20px;
        }

        .countdown-label {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: #7aa8cc;
          margin-bottom: 4px;
        }

        .countdown-value {
          font-size: 2.8rem;
          font-weight: 700;
          color: #ffe84d;
          text-shadow: 0 0 20px rgba(255,232,77,0.35);
          letter-spacing: -0.02em;
          line-height: 1;
          font-variant-numeric: tabular-nums;
          min-height: 1.2em;
          transition: color 0.3s;
        }

        .countdown-value.paid {
          color: #4cff91;
          text-shadow: 0 0 20px rgba(76,255,145,0.35);
        }

        .countdown-sublabel {
          font-size: 0.72rem;
          color: #5585aa;
          margin-top: 4px;
        }

        /* ── Progress bar ── */
        .progress-wrap {
          margin: 12px 0 20px;
        }

        .progress-track {
          background: rgba(255,255,255,0.08);
          border-radius: 100px;
          height: 10px;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          border-radius: 100px;
          background: linear-gradient(90deg, #2a9d8f, #4cff91);
          transition: width 0.6s ease;
          min-width: 2px;
        }

        .progress-label {
          font-size: 0.72rem;
          color: #4cff91;
          text-align: right;
          margin-top: 4px;
        }

        /* ── Live today savings ── */
        .live-today-section {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          margin-bottom: 20px;
          padding: 10px 16px;
          background: rgba(76,255,145,0.07);
          border: 1px solid rgba(76,255,145,0.18);
          border-radius: 10px;
        }

        .live-icon {
          font-size: 1.3rem;
        }

        .live-text {
          text-align: left;
        }

        .live-label {
          font-size: 0.7rem;
          color: #7cc8a0;
          text-transform: uppercase;
          letter-spacing: 0.1em;
        }

        .live-value {
          font-size: 1.4rem;
          font-weight: 700;
          color: #4cff91;
          font-variant-numeric: tabular-nums;
        }

        /* ── Stats grid ── */
        .stats-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          margin-bottom: 16px;
        }

        .stat-box {
          background: rgba(255,255,255,0.05);
          border-radius: 10px;
          padding: 10px 12px;
          border: 1px solid rgba(255,255,255,0.07);
        }

        .stat-label {
          font-size: 0.68rem;
          text-transform: uppercase;
          letter-spacing: 0.1em;
          color: #5a80a0;
          margin-bottom: 3px;
        }

        .stat-value {
          font-size: 1.05rem;
          font-weight: 600;
          color: #c8e8ff;
          font-variant-numeric: tabular-nums;
        }

        /* ── Live rate bar ── */
        .rate-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: rgba(255,200,50,0.06);
          border: 1px solid rgba(255,200,50,0.15);
          border-radius: 10px;
          padding: 8px 14px;
        }

        .rate-left {
          font-size: 0.72rem;
          color: #ffcc44;
          text-transform: uppercase;
          letter-spacing: 0.1em;
        }

        .rate-right {
          display: flex;
          gap: 16px;
          align-items: center;
        }

        .rate-item {
          text-align: center;
        }

        .rate-item .rlabel {
          font-size: 0.62rem;
          color: #9a7a30;
          text-transform: uppercase;
        }

        .rate-item .rvalue {
          font-size: 0.88rem;
          font-weight: 600;
          color: #ffe270;
          font-variant-numeric: tabular-nums;
        }

        .solar-icon {
          font-size: 1.5rem;
          animation: spin 8s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      </style>

      <ha-card>
        <div class="card">

          <!-- Header -->
          <div class="header">
            <span class="solar-icon">☀️</span>
            <h2>${this._config.title}</h2>
            <span class="status-dot" id="status-dot"></span>
          </div>

          <!-- Payback countdown -->
          <div class="countdown-section">
            <div class="countdown-label">Setup Cost Remaining</div>
            <div class="countdown-value" id="live-remaining">—</div>
            <div class="countdown-sublabel">Counting down live as your panels earn</div>
          </div>

          <!-- Progress bar -->
          <div class="progress-wrap">
            <div class="progress-track">
              <div class="progress-fill" id="payback-bar-fill" style="width:0%"></div>
            </div>
            <div class="progress-label" id="pct-label">0.0% paid off</div>
          </div>

          <!-- Live savings today -->
          <div class="live-today-section">
            <div class="live-icon">⚡</div>
            <div class="live-text">
              <div class="live-label">Saved Today (live)</div>
              <div class="live-value" id="live-today">—</div>
            </div>
          </div>

          <!-- Stats grid -->
          <div class="stats-grid">
            <div class="stat-box">
              <div class="stat-label">This Month</div>
              <div class="stat-value" id="stat-month">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Lifetime Total</div>
              <div class="stat-value" id="stat-lifetime">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Setup Cost</div>
              <div class="stat-value" id="stat-setup">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Earning Rate</div>
              <div class="stat-value" id="stat-rate">—</div>
            </div>
          </div>

          <!-- Live rate bar -->
          <div class="rate-bar">
            <div class="rate-left">☀️ Live Solar</div>
            <div class="rate-right">
              <div class="rate-item">
                <div class="rlabel">Watts</div>
                <div class="rvalue" id="stat-watts">—</div>
              </div>
              <div class="rate-item">
                <div class="rlabel">kW</div>
                <div class="rvalue" id="stat-kw">—</div>
              </div>
            </div>
          </div>

        </div>
      </ha-card>
    `;
  }

  // ── Card size hint ───────────────────────────────────────────────────────────
  getCardSize() { return 5; }

  static getConfigElement() {
    return document.createElement("solar-savings-card-editor");
  }

  static getStubConfig() {
    return { title: "Solar Savings" };
  }
}

customElements.define("solar-savings-card", SolarSavingsCard);

// ── Card editor (basic) ────────────────────────────────────────────────────────

class SolarSavingsCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; }
  set hass(hass) { this._hass = hass; }
}
customElements.define("solar-savings-card-editor", SolarSavingsCardEditor);

// ── Register card in HACS ──────────────────────────────────────────────────────

window.customCards = window.customCards || [];
window.customCards.push({
  type: "solar-savings-card",
  name: "Solar Savings Card",
  description:
    "Live ticking payback countdown + daily/monthly savings tracker for your solar installation.",
  preview: false,
  documentationURL: "https://github.com/yourusername/solar-savings-ha",
});
