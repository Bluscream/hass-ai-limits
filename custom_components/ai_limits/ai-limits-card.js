class AILimitsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() {
    return 3;
  }

  render() {
    if (!this._hass) return;

    // 1. Gather all entities and group by account
    const states = this._hass.states;
    const groups = {};

    Object.keys(states).forEach((entityId) => {
      let provider = null;
      let account = null;
      let metric = null;

      if (entityId.startsWith("sensor.claude_subscription_")) {
        provider = "Claude AI";
        const parts = entityId.replace("sensor.claude_subscription_", "").split("_");
        account = parts[0];
        metric = parts.slice(1).join("_");
      } else if (entityId.startsWith("sensor.antigravity_")) {
        provider = "Google AI";
        const parts = entityId.replace("sensor.antigravity_", "").split("_");
        account = parts[0];
        metric = parts.slice(1).join("_");
      } else if (entityId.startsWith("binary_sensor.claude_subscription_")) {
        provider = "Claude AI";
        const parts = entityId.replace("binary_sensor.claude_subscription_", "").split("_");
        account = parts[0];
        metric = parts.slice(1).join("_");
      } else if (entityId.startsWith("binary_sensor.antigravity_")) {
        provider = "Google AI";
        const parts = entityId.replace("binary_sensor.antigravity_", "").split("_");
        account = parts[0];
        metric = parts.slice(1).join("_");
      }

      if (provider && account) {
        const key = `${provider}:${account}`;
        if (!groups[key]) {
          groups[key] = {
            provider,
            account,
            status: "unknown",
            credits: null,
            limits: []
          };
        }

        const stateObj = states[entityId];
        if (metric === "status") {
          groups[key].status = stateObj.state;
        } else if (metric === "ai_credits") {
          groups[key].credits = stateObj.state;
        } else if (metric !== "soonest_reset_in" && metric !== "rate_limited") {
          // If it's a utilization/window sensor (has status/remaining_percent attributes or mdi:gauge icon)
          const attrs = stateObj.attributes || {};
          if (attrs.status || attrs.remaining_percent !== undefined || attrs.icon === "mdi:gauge") {
            groups[key].limits.push({
              name: attrs.friendly_name || stateObj.entity_id,
              cleanName: this._getCleanName(attrs.friendly_name, provider, account),
              state: stateObj.state,
              status: attrs.status || "unknown",
              remaining: attrs.remaining_percent,
              utilization: attrs.utilization_percent
            });
          }
        }
      }
    });

    // 2. Render Card HTML
    let html = `
      <style>
        ha-card {
          padding: 16px;
        }
        .title {
          font-size: 16px;
          font-weight: bold;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .account-group {
          margin-bottom: 16px;
        }
        .account-group:last-child {
          margin-bottom: 0;
        }
        .account-header {
          font-weight: bold;
          margin-bottom: 6px;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .credits {
          font-size: 0.9em;
          color: var(--secondary-text-color);
        }
        .limit-list {
          list-style: none;
          padding: 0 0 0 12px;
          margin: 0;
        }
        .limit-item {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 4px 0;
          font-size: 14px;
        }
        .status-dot {
          display: inline-block;
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .status-within_limit {
          background-color: var(--success-color, #2ecc71);
        }
        .status-exhausted {
          background-color: var(--error-color, #e74c3c);
        }
        .status-unknown {
          background-color: var(--warning-color, #f1c40f);
        }
      </style>
      <ha-card>
        <div class="title">
          <ha-icon icon="mdi:gauge"></ha-icon>
          <span>AI Limits</span>
        </div>
    `;

    const keys = Object.keys(groups);
    if (keys.length === 0) {
      html += `<div>No AI Limit accounts found. Check integration configuration.</div>`;
    } else {
      keys.forEach((key) => {
        const group = groups[key];
        const creditsStr = group.credits !== null ? ` (🪙 ${group.credits})` : "";
        html += `
          <div class="account-group">
            <div class="account-header">
              <span><strong>${group.provider} (${group.account})</strong></span>
              <span class="credits">${creditsStr}</span>
            </div>
            <ul class="limit-list">
        `;

        group.limits.forEach((limit) => {
          const dotClass = limit.status === "exhausted" ? "status-exhausted" : "status-within_limit";
          html += `
            <li class="limit-item">
              <span class="status-dot ${dotClass}"></span>
              <span><strong>${limit.cleanName}</strong>: ${limit.state}</span>
            </li>
          `;
        });

        html += `
            </ul>
          </div>
        `;
      });
    }

    html += `</ha-card>`;
    this.shadowRoot.innerHTML = html;
  }

  _getCleanName(friendlyName, provider, account) {
    if (!friendlyName) return "Limit";
    // Strip prefixes
    let clean = friendlyName;
    clean = clean.replace(`Claude subscription - ${account} `, "");
    clean = clean.replace(`Antigravity - ${account} `, "");
    // Capitalize first letter
    return clean.charAt(0).toUpperCase() + clean.slice(1);
  }
}

customElements.define("ai-limits-card", AILimitsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ai-limits-card",
  name: "AI Limits Card",
  description: "Displays your Claude and Google Gemini usage limits.",
  preview: true,
});
