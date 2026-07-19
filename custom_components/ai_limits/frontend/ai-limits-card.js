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

    const okColor = this._config.ok_color || "var(--success-color, #2ecc71)";
    const exhaustedColor = this._config.exhausted_color || "var(--error-color, #e74c3c)";
    const exhaustedBgColor = this._config.exhausted_bg_color || "var(--secondary-text-color, #7f8c8d)";

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
        .brand-logo {
          width: 16px;
          height: 16px;
          flex-shrink: 0;
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
          background-color: ${okColor};
        }
        .status-exhausted {
          background-color: ${exhaustedColor};
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
          background-color: ${okColor};
        }
        .progress-bar.striped {
          background-image: linear-gradient(
            45deg,
            ${exhaustedColor} 25%,
            ${exhaustedBgColor} 25%,
            ${exhaustedBgColor} 50%,
            ${exhaustedColor} 50%,
            ${exhaustedColor} 75%,
            ${exhaustedBgColor} 75%,
            ${exhaustedBgColor}
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
          // If title and icon are both empty or evaluated to falsy, do not render header
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
        
        const isClaude = group.provider === "Claude AI";
        const isGoogle = group.provider === "Google AI" || group.provider.includes("Google") || group.provider.includes("Gemini");
        
        let logoHtml = "";
        if (isClaude) {
          logoHtml = `<svg class="brand-logo" viewBox="0 0 24 24" style="fill: #ea743b;"><path d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z\"/></svg>`;
        } else if (isGoogle) {
          logoHtml = `<svg class="brand-logo" viewBox="0 0 24 24" style="fill: #38A3E8;"><path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81\"/></svg>`;
        }
        
        html += `
          <div class="account-group">
            <div class="account-header">
              ${logoHtml}
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
