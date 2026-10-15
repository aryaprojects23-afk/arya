/**
 * HarvestLink 2.0 - Government Mandi Prices Module
 * Displays official APMC mandi wholesale records, data freshness states,
 * nearby market comparisons, and historical price trend charts.
 */

const MandiDashboard = {
  filters: {
    state: "Andhra Pradesh",
    district: "Chittoor",
    market: "",
    commodity: "",
    date: "",
    search: ""
  },

  async init() {
    await this.loadFiltersData();
    this.bindEvents();
    await this.fetchAndRenderPrices();
    await this.loadHistoricalTrends("Tomato", "Chittoor APMC");
    await this.loadNearbyMandis("Andhra Pradesh", "Chittoor", "Tomato");
    await this.checkProviderStatus();
  },

  async loadFiltersData() {
    try {
      const res = await fetch("/api/market-prices/filters");
      const data = await res.json();
      
      const stateSel = document.getElementById("mandi-filter-state");
      const distSel = document.getElementById("mandi-filter-district");
      const commSel = document.getElementById("mandi-filter-commodity");

      if (stateSel) {
        stateSel.innerHTML = '<option value="">All States</option>';
        data.states.forEach(s => {
          const opt = document.createElement("option");
          opt.value = s;
          opt.textContent = s;
          if (s === this.filters.state) opt.selected = true;
          stateSel.appendChild(opt);
        });
      }

      this.updateDistrictDropdown(data.districts_by_state);

      if (commSel) {
        commSel.innerHTML = '<option value="">All Commodities</option>';
        data.commodities.forEach(c => {
          const opt = document.createElement("option");
          opt.value = c;
          opt.textContent = c;
          commSel.appendChild(opt);
        });
      }

      this.districtsMap = data.districts_by_state || {};
    } catch (e) {
      console.error("Error loading mandi filters:", e);
    }
  },

  updateDistrictDropdown(districtsMap) {
    const distSel = document.getElementById("mandi-filter-district");
    if (!distSel) return;
    const currentState = this.filters.state;
    const districts = districtsMap ? districtsMap[currentState] || [] : [];
    
    distSel.innerHTML = '<option value="">All Districts</option>';
    districts.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = d;
      if (d === this.filters.district) opt.selected = true;
      distSel.appendChild(opt);
    });
  },

  bindEvents() {
    const applyBtn = document.getElementById("btn-apply-mandi-filters");
    if (applyBtn) {
      applyBtn.addEventListener("click", () => {
        this.filters.state = document.getElementById("mandi-filter-state")?.value || "";
        this.filters.district = document.getElementById("mandi-filter-district")?.value || "";
        this.filters.commodity = document.getElementById("mandi-filter-commodity")?.value || "";
        this.filters.search = document.getElementById("mandi-search-input")?.value || "";
        this.fetchAndRenderPrices();
        if (this.filters.commodity) {
          this.loadHistoricalTrends(this.filters.commodity);
          this.loadNearbyMandis(this.filters.state || "Andhra Pradesh", this.filters.district || "Chittoor", this.filters.commodity);
        }
      });
    }

    const resetBtn = document.getElementById("btn-reset-mandi-filters");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        this.filters = { state: "Andhra Pradesh", district: "Chittoor", market: "", commodity: "", date: "", search: "" };
        document.getElementById("mandi-filter-state").value = "Andhra Pradesh";
        this.updateDistrictDropdown(this.districtsMap);
        document.getElementById("mandi-filter-district").value = "Chittoor";
        document.getElementById("mandi-filter-commodity").value = "";
        document.getElementById("mandi-search-input").value = "";
        this.fetchAndRenderPrices();
      });
    }

    const syncBtn = document.getElementById("btn-sync-gov-data");
    if (syncBtn) {
      syncBtn.addEventListener("click", async () => {
        const originalText = syncBtn.textContent;
        syncBtn.disabled = true;
        syncBtn.textContent = I18n.t("mandi.syncing", "Synchronizing with Government Portal...");
        
        try {
          const res = await fetch("/api/market-prices/sync", { method: "POST" });
          const result = await res.json();
          App.showToast(result.message, result.status === "SUCCESS" ? "success" : "info");
          await this.fetchAndRenderPrices();
          await this.checkProviderStatus();
        } catch (e) {
          App.showToast("Sync request error. Serving cached government records.", "warning");
        } finally {
          syncBtn.disabled = false;
          syncBtn.textContent = originalText;
        }
      });
    }

    const stateSel = document.getElementById("mandi-filter-state");
    if (stateSel) {
      stateSel.addEventListener("change", (e) => {
        this.filters.state = e.target.value;
        this.updateDistrictDropdown(this.districtsMap);
      });
    }
  },

  async fetchAndRenderPrices() {
    const tbody = document.getElementById("mandi-table-body");
    const freshnessBanner = document.getElementById("mandi-freshness-banner");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 24px;">${I18n.t("common.loading", "Loading government records...")}</td></tr>`;

    try {
      const params = new URLSearchParams();
      if (this.filters.state) params.append("state", this.filters.state);
      if (this.filters.district) params.append("district", this.filters.district);
      if (this.filters.commodity) params.append("commodity", this.filters.commodity);
      if (this.filters.search) params.append("search", this.filters.search);

      const res = await fetch(`/api/market-prices?${params.toString()}`);
      const result = await res.json();
      const records = result.data || [];

      // Update Freshness status banner
      if (freshnessBanner) {
        if (result.data_freshness.includes("Fresh") || result.data_freshness.includes("Live")) {
          freshnessBanner.className = "alert-banner success";
          freshnessBanner.innerHTML = `<span><strong>${I18n.t("mandi.live_fresh", "Live & Fresh Official Mandi Data")}</strong>: Verified APMC prices reported under Agmarknet DMI standards. Showing ${records.length} records.</span>`;
        } else {
          freshnessBanner.className = "alert-banner stale";
          freshnessBanner.innerHTML = `<span><strong>${I18n.t("mandi.stale_warning", "Historical / Cached Data")}</strong>: Currently displaying most recently synchronized APMC records. Live portal update pending.</span>`;
        }
      }

      if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 30px; color: #64748b;">${I18n.t("mandi.no_data", "No official market records found for the selected criteria.")}</td></tr>`;
        return;
      }

      tbody.innerHTML = "";
      records.forEach(r => {
        const tr = document.createElement("tr");
        const kgEquiv = (r.modal_price / 100.0).toFixed(2);
        const isFresh = r.freshness_status === "Live" || r.freshness_status === "Fresh";
        
        tr.innerHTML = `
          <td><strong>${r.commodity_name}</strong> <br><small style="color:#64748b;">${r.variety} (${r.grade})</small></td>
          <td><strong>${r.market_name}</strong><br><small>${r.district}</small></td>
          <td>${r.state}</td>
          <td>₹${r.min_price.toLocaleString("en-IN")}</td>
          <td>₹${r.max_price.toLocaleString("en-IN")}</td>
          <td><strong style="color:var(--primary-dark); font-size:15px;">₹${r.modal_price.toLocaleString("en-IN")}</strong></td>
          <td><span style="background-color:var(--primary-soft); color:var(--primary-dark); padding:2px 6px; border-radius:4px; font-weight:700;">₹${kgEquiv}</span></td>
          <td>${r.arrivals_in_tonnes ? r.arrivals_in_tonnes + ' T' : '—'}</td>
          <td>${r.arrival_date}</td>
        `;
        tbody.appendChild(tr);
      });

    } catch (e) {
      console.error("Failed to render mandi table:", e);
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 24px; color:#ef4444;">Failed to load records. Check connection.</td></tr>`;
    }
  },

  async loadHistoricalTrends(commodity = "Tomato", market = "") {
    const chartContainer = document.getElementById("mandi-trend-chart-container");
    if (!chartContainer) return;

    try {
      const res = await fetch(`/api/market-prices/trends?commodity=${encodeURIComponent(commodity)}&days=30`);
      const data = await res.json();
      const points = data.trends || [];

      if (points.length < 2) {
        chartContainer.innerHTML = `<p style="padding: 20px; color: #64748b; text-align:center;">Insufficient historical records for trend projection.</p>`;
        return;
      }

      // Render lightweight responsive SVG Trend Chart
      const maxP = Math.max(...points.map(p => p.modal_price));
      const minP = Math.min(...points.map(p => p.modal_price));
      const range = (maxP - minP) || 1;
      const width = 700;
      const height = 220;
      const padding = 40;

      const coords = points.map((p, idx) => {
        const x = padding + (idx / (points.length - 1)) * (width - padding * 2);
        const y = height - padding - ((p.modal_price - minP) / range) * (height - padding * 2);
        return { x, y, price: p.modal_price, date: p.date };
      });

      const pathData = coords.reduce((acc, c, idx) => `${acc} ${idx === 0 ? 'M' : 'L'} ${c.x} ${c.y}`, "");

      chartContainer.innerHTML = `
        <div style="margin-bottom: 12px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong>${commodity} Modal Price Trend (${data.date_range})</strong>
            <div style="font-size:12px; color:#64748b;">Average: ₹${data.summary.average_modal_price}/Q | Min: ₹${data.summary.lowest_min_price}/Q | Max: ₹${data.summary.highest_max_price}/Q</div>
          </div>
          <span class="badge badge-verified">${points.length} Reporting Days</span>
        </div>
        <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: auto; background:#fafafa; border-radius:8px; border:1px solid #e2e8f0;">
          <!-- Grid lines -->
          <line x1="${padding}" y1="${padding}" x2="${width-padding}" y2="${padding}" stroke="#e2e8f0" stroke-dasharray="4"/>
          <line x1="${padding}" y1="${height/2}" x2="${width-padding}" y2="${height/2}" stroke="#e2e8f0" stroke-dasharray="4"/>
          <line x1="${padding}" y1="${height-padding}" x2="${width-padding}" y2="${height-padding}" stroke="#cbd5e1"/>
          
          <!-- Price Path -->
          <path d="${pathData}" fill="none" stroke="var(--primary)" stroke-width="3" stroke-linecap="round"/>
          
          <!-- Data Points -->
          ${coords.map(c => `
            <circle cx="${c.x}" cy="${c.y}" r="4" fill="var(--primary-dark)"/>
          `).join("")}
          
          <!-- Axis labels -->
          <text x="${padding}" y="${padding - 8}" font-size="11" fill="#64748b">₹${maxP}/Q</text>
          <text x="${padding}" y="${height - padding + 18}" font-size="11" fill="#64748b">₹${minP}/Q</text>
          <text x="${coords[0].x}" y="${height - 10}" font-size="10" fill="#64748b">${coords[0].date.slice(5)}</text>
          <text x="${coords[coords.length-1].x - 30}" y="${height - 10}" font-size="10" fill="#64748b">${coords[coords.length-1].date.slice(5)}</text>
        </svg>
      `;

    } catch (e) {
      console.error("Error loading mandi trends:", e);
    }
  },

  async loadNearbyMandis(state, district, commodity) {
    const container = document.getElementById("nearby-mandis-container");
    if (!container) return;

    try {
      const res = await fetch(`/api/market-prices/nearby?state=${encodeURIComponent(state)}&district=${encodeURIComponent(district)}&commodity=${encodeURIComponent(commodity)}`);
      const data = await res.json();
      const mandis = data.nearby_mandis || [];

      if (mandis.length === 0) {
        container.innerHTML = `<p style="color:#64748b; font-size:13px;">No neighboring mandis reporting ${commodity} in ${district}.</p>`;
        return;
      }

      container.innerHTML = `
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">
          ${mandis.slice(0, 4).map(m => `
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
              <div style="font-weight:700; color:var(--primary-dark); font-size:14px;">${m.market_name}</div>
              <div style="font-size:12px; color:#64748b; margin-bottom:6px;">${m.district}, ${m.state}</div>
              <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <span style="font-size:16px; font-weight:800; color:var(--primary);">₹${m.modal_price}/Q</span>
                <span style="font-size:12px; font-weight:600; color:#15803d;">₹${(m.modal_price/100).toFixed(1)}/kg</span>
              </div>
              <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Date: ${m.arrival_date}</div>
            </div>
          `).join("")}
        </div>
      `;

    } catch (e) {
      console.error("Failed to load nearby mandis:", e);
    }
  },

  async checkProviderStatus() {
    const el = document.getElementById("provider-health-badge");
    if (!el) return;
    try {
      const res = await fetch("/api/market-prices/status");
      const status = await res.json();
      if (status.is_healthy) {
        el.className = "badge badge-live";
        el.textContent = `OGD Portal: Active (${status.total_records_cached} cached records)`;
      } else {
        el.className = "badge badge-stale";
        el.textContent = `OGD Portal: Offline Fallback (${status.total_records_cached} cached records)`;
      }
    } catch (e) {
      el.className = "badge badge-stale";
      el.textContent = "OGD Portal: Local Fallback Cache";
    }
  }
};

window.MandiDashboard = MandiDashboard;
