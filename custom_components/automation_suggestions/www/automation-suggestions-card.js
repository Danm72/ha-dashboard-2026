/**
 * Automation Suggestions Card
 * Displays all automation suggestions with domain grouping, dismiss buttons, and scan trigger.
 */

const DOMAIN_EMOJI = {
  light: "💡",
  switch: "🔌",
  cover: "🚪",
  climate: "🌡️",
  scene: "🎬",
  script: "📜",
  input_number: "⚙️",
  input_boolean: "⚙️",
  input_select: "⚙️",
  input_datetime: "⚙️",
  input_button: "⚙️",
};

const DEFAULT_EMOJI = "📋";

class AutomationSuggestionsCard extends HTMLElement {
  // Internal state
  _hass = null;
  _config = null;
  _suggestions = [];
  _total = 0;
  _page = 1;
  _pages = 0;
  _scanning = false;
  _loading = true;
  _error = null;
  _unsubscribe = null;
  _collapsedDomains = new Set();
  _boundHandleClick = null;

  // Memoization cache
  _groupedCache = null;
  _groupedCacheKey = null;

  static getStubConfig() {
    return { page_size: 20 };
  }

  setConfig(config) {
    this._config = { page_size: 20, ...config };
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

    // Only re-render if hass actually changed (prevents excessive renders)
    if (oldHass === null || hass.language !== oldHass.language) {
      this._render();
    }
  }

  connectedCallback() {
    // Set up event delegation
    this._boundHandleClick = this._handleClick.bind(this);
    this.addEventListener("click", this._boundHandleClick);

    // Subscribe to WebSocket updates
    this._subscribeToUpdates();
  }

  disconnectedCallback() {
    // Clean up event listeners
    if (this._boundHandleClick) {
      this.removeEventListener("click", this._boundHandleClick);
      this._boundHandleClick = null;
    }

    // Unsubscribe from WebSocket
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
  }

  async _subscribeToUpdates() {
    if (!this._hass) return;

    try {
      this._unsubscribe = await this._hass.connection.subscribeMessage(
        (msg) => {
          this._suggestions = msg.suggestions || [];
          this._total = msg.total || 0;
          this._loading = false;
          this._invalidateGroupCache();
          this._render();
        },
        { type: "automation_suggestions/subscribe" }
      );
    } catch (err) {
      this._error = err.message;
      this._loading = false;
      this._render();
    }
  }

  _handleClick(event) {
    const target = event.target.closest("[data-action]") || event.target;

    // Dismiss button
    if (target.classList.contains("dismiss-btn")) {
      const suggestionId = target.dataset.suggestionId;
      if (suggestionId) this._dismiss(suggestionId);
      return;
    }

    // Scan Now button
    if (target.classList.contains("scan-btn")) {
      this._scanNow();
      return;
    }

    // Domain header (collapse toggle)
    if (target.classList.contains("domain-header") || target.closest(".domain-header")) {
      const header = target.closest(".domain-header") || target;
      const domain = header.dataset.domain;
      if (domain) this._toggleDomain(domain);
      return;
    }

    // Pagination
    if (target.classList.contains("page-prev") && this._page > 1) {
      this._page--;
      this._fetchPage();
      return;
    }
    if (target.classList.contains("page-next") && this._page < this._pages) {
      this._page++;
      this._fetchPage();
      return;
    }

    // Retry button
    if (target.classList.contains("retry-btn")) {
      this._error = null;
      this._loading = true;
      this._render();
      this._subscribeToUpdates();
    }
  }

  async _dismiss(suggestionId) {
    try {
      await this._hass.callService("automation_suggestions", "dismiss", {
        suggestion_id: suggestionId,
      });
    } catch (err) {
      console.error("Failed to dismiss suggestion:", err);
    }
  }

  async _scanNow() {
    // Re-entry guard: prevent double-clicks
    if (this._scanning) return;

    this._scanning = true;
    this._render();

    try {
      await this._hass.callService("automation_suggestions", "analyze_now", {});
    } catch (err) {
      console.error("Failed to trigger scan:", err);
      this._error = "Scan failed. Please try again.";
    } finally {
      this._scanning = false;
      this._render();
    }
  }

  _toggleDomain(domain) {
    if (this._collapsedDomains.has(domain)) {
      this._collapsedDomains.delete(domain);
    } else {
      this._collapsedDomains.add(domain);
    }
    this._render();
  }

  async _fetchPage() {
    this._loading = true;
    this._render();

    try {
      const result = await this._hass.callWS({
        type: "automation_suggestions/list",
        page: this._page,
        page_size: this._config.page_size,
      });
      this._suggestions = result.suggestions;
      this._total = result.total;
      this._pages = result.pages;
      this._loading = false;
      this._invalidateGroupCache();
    } catch (err) {
      this._error = err.message;
      this._loading = false;
    }
    this._render();
  }

  _invalidateGroupCache() {
    this._groupedCache = null;
    this._groupedCacheKey = null;
  }

  _groupByDomain(suggestions) {
    // Memoization: only recompute if suggestions changed
    const cacheKey = JSON.stringify(suggestions.map((s) => s.id));
    if (this._groupedCacheKey === cacheKey && this._groupedCache) {
      return this._groupedCache;
    }

    const grouped = {};
    for (const s of suggestions) {
      const domain = s.entity_id?.split(".")[0] || "unknown";
      if (!grouped[domain]) grouped[domain] = [];
      grouped[domain].push(s);
    }

    // Sort domains by count descending
    const sorted = Object.entries(grouped).sort((a, b) => b[1].length - a[1].length);

    this._groupedCache = sorted;
    this._groupedCacheKey = cacheKey;
    return sorted;
  }

  _render() {
    if (!this._hass) return;

    // Loading state
    if (this._loading) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content loading">
            <ha-circular-progress indeterminate></ha-circular-progress>
            <span>Loading suggestions...</span>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Error state
    if (this._error) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content error">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <span>${this._escapeHtml(this._error)}</span>
            <mwc-button class="retry-btn">Retry</mwc-button>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Empty state
    if (this._suggestions.length === 0) {
      this.innerHTML = `
        <ha-card>
          <div class="card-header">Automation Suggestions</div>
          <div class="card-content empty">
            <ha-icon icon="mdi:lightbulb-outline"></ha-icon>
            <span>No suggestions yet.</span>
            <span class="empty-hint">Click Scan Now to analyze your usage patterns.</span>
            <mwc-button class="scan-btn" ${this._scanning ? "disabled" : ""}>
              ${this._scanning ? "Scanning..." : "Scan Now"}
            </mwc-button>
          </div>
        </ha-card>
      `;
      this._applyStyles();
      return;
    }

    // Main content
    const grouped = this._groupByDomain(this._suggestions);

    let domainsHtml = "";
    for (const [domain, suggestions] of grouped) {
      const emoji = DOMAIN_EMOJI[domain] || DEFAULT_EMOJI;
      const isCollapsed = this._collapsedDomains.has(domain);
      const collapseIcon = isCollapsed ? "mdi:chevron-right" : "mdi:chevron-down";
      const domainLabel = domain.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

      let suggestionsHtml = "";
      if (!isCollapsed) {
        for (const s of suggestions) {
          const name = this._escapeHtml(s.friendly_name || s.entity_id);
          const action = this._escapeHtml((s.action || "").replace(/_/g, " "));
          const pct = Math.round((s.consistency_score || 0) * 100);
          const time = this._escapeHtml(s.suggested_time || "");
          suggestionsHtml += `
            <div class="suggestion">
              <div class="suggestion-main">
                <span class="action">${action}</span>
                <span class="name">${name}</span>
                <span class="time">around ${time}</span>
              </div>
              <div class="suggestion-meta">
                ${pct}% consistent, seen ${s.occurrence_count} times
              </div>
              <button class="dismiss-btn" data-suggestion-id="${this._escapeHtml(s.id)}" title="Dismiss">
                <ha-icon icon="mdi:close"></ha-icon>
              </button>
            </div>
          `;
        }
      }

      domainsHtml += `
        <div class="domain-section">
          <div class="domain-header" data-domain="${this._escapeHtml(domain)}">
            <ha-icon icon="${collapseIcon}"></ha-icon>
            <span class="domain-emoji">${emoji}</span>
            <span class="domain-name">${domainLabel}</span>
            <span class="domain-count">(${suggestions.length})</span>
          </div>
          <div class="domain-suggestions ${isCollapsed ? "collapsed" : ""}">
            ${suggestionsHtml}
          </div>
        </div>
      `;
    }

    // Pagination
    let paginationHtml = "";
    if (this._pages > 1) {
      paginationHtml = `
        <div class="pagination">
          <button class="page-prev" ${this._page <= 1 ? "disabled" : ""}>
            <ha-icon icon="mdi:chevron-left"></ha-icon>
          </button>
          <span>Page ${this._page} of ${this._pages}</span>
          <button class="page-next" ${this._page >= this._pages ? "disabled" : ""}>
            <ha-icon icon="mdi:chevron-right"></ha-icon>
          </button>
        </div>
      `;
    }

    this.innerHTML = `
      <ha-card>
        <div class="card-header">
          Automation Suggestions
          <span class="total-count">(${this._total} total)</span>
        </div>
        <div class="card-content">
          ${domainsHtml}
        </div>
        <div class="card-actions">
          <mwc-button class="scan-btn" ${this._scanning ? "disabled" : ""}>
            ${this._scanning ? "Scanning..." : "Scan Now"}
          </mwc-button>
          ${paginationHtml}
        </div>
      </ha-card>
    `;
    this._applyStyles();
  }

  _escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _applyStyles() {
    // Only add styles once
    if (this.querySelector("style")) return;

    const style = document.createElement("style");
    style.textContent = `
      ha-card {
        padding: 0;
      }
      .card-header {
        padding: 16px;
        font-size: 1.2em;
        font-weight: 500;
        border-bottom: 1px solid var(--divider-color);
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .total-count {
        font-size: 0.8em;
        color: var(--secondary-text-color);
        font-weight: normal;
      }
      .card-content {
        padding: 8px 16px;
      }
      .card-content.loading,
      .card-content.empty,
      .card-content.error {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 16px;
        padding: 32px;
        text-align: center;
        color: var(--secondary-text-color);
      }
      .empty-hint {
        font-size: 0.9em;
        opacity: 0.8;
      }
      .domain-section {
        margin-bottom: 8px;
      }
      .domain-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        cursor: pointer;
        border-radius: 4px;
        font-weight: 500;
      }
      .domain-header:hover {
        background: var(--secondary-background-color);
      }
      .domain-count {
        color: var(--secondary-text-color);
        font-weight: normal;
      }
      .domain-suggestions.collapsed {
        display: none;
      }
      .suggestion {
        display: grid;
        grid-template-columns: 1fr auto;
        grid-template-rows: auto auto;
        gap: 4px;
        padding: 8px 8px 8px 40px;
        border-bottom: 1px solid var(--divider-color);
      }
      .suggestion:last-child {
        border-bottom: none;
      }
      .suggestion-main {
        grid-column: 1;
        grid-row: 1;
      }
      .suggestion-meta {
        grid-column: 1;
        grid-row: 2;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }
      .dismiss-btn {
        grid-column: 2;
        grid-row: 1 / span 2;
        align-self: center;
        background: none;
        border: none;
        cursor: pointer;
        padding: 8px;
        border-radius: 50%;
        color: var(--secondary-text-color);
      }
      .dismiss-btn:hover {
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }
      .action {
        text-transform: capitalize;
      }
      .card-actions {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        border-top: 1px solid var(--divider-color);
      }
      .pagination {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .pagination button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        border-radius: 50%;
        color: var(--secondary-text-color);
      }
      .pagination button:hover:not([disabled]) {
        background: var(--secondary-background-color);
      }
      .pagination button[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
      }
    `;
    this.prepend(style);
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("automation-suggestions-card", AutomationSuggestionsCard);

// Register for card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "automation-suggestions-card",
  name: "Automation Suggestions",
  description: "View and manage all automation suggestions with grouping and dismiss controls",
});
