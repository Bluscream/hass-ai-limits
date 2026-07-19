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

  static getStubConfig() {
    return {
      type: "custom:ai-limits-card",
      title: "AI Limits",
      icon: "mdi:gauge",
      show_header: true
    };
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
              utilization: attrs.utilization_percent,
              resetsIn: attrs.resets_in_seconds,
              metricKey: metric
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
          flex-direction: column;
          margin: 8px 0;
          font-size: 14px;
        }
        .limit-label {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
        }
        .limit-name {
          display: flex;
          align-items: center;
          gap: 8px;
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
        .progress-bar-container {
          width: 100%;
          background-color: var(--secondary-background-color, #e0e0e0);
          border-radius: 4px;
          height: 6px;
          overflow: hidden;
          margin-top: 4px;
        }
        .progress-bar {
          height: 100%;
          border-radius: 4px;
          transition: width 0.3s ease;
        }
        .progress-bar.green {
          background-color: var(--success-color, #2ecc71);
        }
        .progress-bar.striped {
          background-image: linear-gradient(
            45deg,
            #e74c3c 25%,
            #7f8c8d 25%,
            #7f8c8d 50%,
            #e74c3c 50%,
            #e74c3c 75%,
            #7f8c8d 75%,
            #7f8c8d
          );
          background-size: 20px 20px;
          animation: stripes 1.5s linear infinite;
        }
        @keyframes stripes {
          from { background-position: 0 0; }
          to { background-position: 20px 0; }
        }
      </style>
      <ha-card>
        ${(() => {
          const showHeader = this._config.show_header !== false;
          const title = this._config.title !== undefined ? this._config.title : "AI Limits";
          const icon = this._config.icon !== undefined ? this._config.icon : "mdi:gauge";
          if (showHeader && (title || icon)) {
            return `
              <div class="title">
                ${icon ? `<ha-icon icon="${icon}"></ha-icon>` : ""}
                ${title ? `<span>${title}</span>` : ""}
              </div>
            `;
          }
          return "";
        })()}
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
            <div class="limit-list">
        `;

        group.limits.forEach((limit) => {
          const isExhausted = limit.status === "exhausted";
          const dotClass = isExhausted ? "status-exhausted" : "status-within_limit";
          
          let barWidth = 100;
          let barClass = "green";

          if (isExhausted) {
            barClass = "striped";
            // Guess total seconds to compute progress towards reset
            let totalSecs = 0;
            if (limit.metricKey.includes("5_hour") || limit.metricKey.includes("5h")) {
              totalSecs = 5 * 3600;
            } else if (limit.metricKey.includes("7_day") || limit.metricKey.includes("7d") || limit.metricKey.includes("weekly_fable")) {
              totalSecs = 7 * 24 * 3600;
            } else {
              totalSecs = 5 * 3600; // Default Google AI Antigravity window
            }

            if (limit.resetsIn && totalSecs) {
              barWidth = Math.max(0, Math.min(100, 100 * (1 - limit.resetsIn / totalSecs)));
            }
          } else {
            barWidth = limit.remaining !== undefined ? limit.remaining : 100;
          }

          html += `
            <div class="limit-item">
              <div class="limit-label">
                <div class="limit-name">
                  <span class="status-dot ${dotClass}"></span>
                  <span><strong>${limit.cleanName}</strong></span>
                </div>
                <span>${limit.state}</span>
              </div>
              <div class="progress-bar-container">
                <div class="progress-bar ${barClass}" style="width: ${barWidth}%"></div>
              </div>
            </div>
          `;
        });

        html += `
            </div>
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
