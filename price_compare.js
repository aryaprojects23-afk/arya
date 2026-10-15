/**
 * HarvestLink 2.0 - "Know Your Mandi Price" Calculator Module
 * Enables farmers to benchmark their farm gate selling price against official Agmarknet wholesale modal rates.
 */

const PriceCompare = {
  async init() {
    this.bindEvents();
    await this.loadCommoditiesDropdown();
  },

  async loadCommoditiesDropdown() {
    const sel = document.getElementById("compare-crop-select");
    if (!sel) return;

    try {
      const res = await fetch("/api/commodities");
      const data = await res.json();
      sel.innerHTML = '<option value="">-- Choose Agricultural Produce --</option>';
      data.commodities.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `${c.canonical_name} (${c.category})`;
        if (c.id === "tomato") opt.selected = true;
        sel.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load commodities for comparison:", e);
    }
  },

  bindEvents() {
    const btn = document.getElementById("btn-run-comparison");
    if (btn) {
      btn.addEventListener("click", () => this.runComparison());
    }
  },

  async runComparison() {
    const cropId = document.getElementById("compare-crop-select")?.value;
    const variety = document.getElementById("compare-variety-input")?.value || "Standard";
    const grade = document.getElementById("compare-grade-select")?.value || "Grade A";
    const state = document.getElementById("compare-state-input")?.value || "Andhra Pradesh";
    const district = document.getElementById("compare-district-input")?.value || "Chittoor";
    const proposedPrice = parseFloat(document.getElementById("compare-price-input")?.value || "0");
    const quantity = parseFloat(document.getElementById("compare-qty-input")?.value || "0");
    const unit = document.getElementById("compare-unit-select")?.value || "kg";

    const resultContainer = document.getElementById("compare-result-container");
    if (!resultContainer) return;

    if (!cropId || proposedPrice <= 0 || quantity <= 0) {
      App.showToast("Please enter a valid crop, proposed price, and quantity.", "warning");
      return;
    }

    resultContainer.innerHTML = `<div style="text-align:center; padding: 40px; color: var(--text-light);">${I18n.t("common.loading", "Calculating comparative benchmark...")}</div>`;

    try {
      const res = await fetch("/api/market-prices/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          commodity_id: cropId,
          variety: variety,
          grade: grade,
          state: state,
          district: district,
          proposed_price: proposedPrice,
          quantity: quantity,
          unit: unit
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Price comparison failed.");
      }

      const comp = await res.json();
      this.renderComparisonResult(comp);

    } catch (e) {
      resultContainer.innerHTML = `
        <div class="alert-banner warning">
          <span>${e.message}</span>
        </div>
      `;
    }
  },

  renderComparisonResult(c) {
    const container = document.getElementById("compare-result-container");
    if (!container) return;

    const isAbove = c.comparison_sentiment === "above_modal";
    const isBelow = c.comparison_sentiment === "below_modal";
    const sentimentClass = isAbove ? "above" : (isBelow ? "below" : "at");

    container.innerHTML = `
      <div class="calc-result-box ${sentimentClass}">
        <!-- Sentiment Banner -->
        <div class="variance-hero ${sentimentClass}">
          <div style="font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">
            ${c.status_label}
          </div>
          <div class="variance-num">
            ${c.price_difference_per_kg >= 0 ? '+' : ''}₹${c.price_difference_per_kg.toFixed(2)}/kg
          </div>
          <div style="font-size: 13px;">
            ${isAbove ? I18n.t("compare.sentiment_above", "Pricing above official mandi modal rate").replace("{percent}", c.percentage_difference) :
              (isBelow ? I18n.t("compare.sentiment_below", "Pricing below official mandi modal rate").replace("{percent}", Math.abs(c.percentage_difference)) :
               I18n.t("compare.sentiment_at", "Pricing identical to mandi modal rate"))}
          </div>
        </div>

        <!-- Metrics Comparison Grid -->
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">
          <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:14px; border-radius:8px;">
            <div style="font-size:12px; color:#64748b; font-weight:600;">YOUR PROPOSED FARM PRICE</div>
            <div style="font-size:20px; font-weight:800; color:var(--primary-dark);">
              ₹${c.farmer_proposed_price_per_kg.toFixed(2)} <span style="font-size:13px; font-weight:normal;">/kg</span>
            </div>
            <div style="font-size:12px; color:#64748b;">(₹${c.farmer_proposed_price_per_input_unit} per ${c.input_unit})</div>
          </div>

          <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:14px; border-radius:8px;">
            <div style="font-size:12px; color:#166534; font-weight:600;">GOVT MANDI MODAL RATE</div>
            <div style="font-size:20px; font-weight:800; color:#15803d;">
              ₹${c.mandi_modal_price_per_kg.toFixed(2)} <span style="font-size:13px; font-weight:normal;">/kg</span>
            </div>
            <div style="font-size:12px; color:#166534;">(₹${c.mandi_modal_price_per_quintal.toFixed(0)} / Quintal)</div>
          </div>
        </div>

        <!-- Gross Revenue Impact -->
        <div style="background:#ffffff; border:1.5px solid #e2e8f0; border-radius:8px; padding:16px; margin-bottom:20px;">
          <div style="font-weight:700; color:var(--primary-dark); margin-bottom:10px; font-size:15px;">Estimated Revenue Impact (${c.normalized_quantity_kg.toFixed(0)} kg total)</div>
          <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px;">
            <span>${I18n.t("compare.farmer_gross_label", "Your Estimated Gross Revenue")}:</span>
            <strong>₹${c.farmer_gross_sale_value.toLocaleString("en-IN")}</strong>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px; color:#475569;">
            <span>${I18n.t("compare.mandi_gross_label", "Revenue at Mandi Modal Rate")}:</span>
            <span>₹${c.mandi_equivalent_gross_value.toLocaleString("en-IN")}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-top:8px; border-top:1px dashed #cbd5e1; font-size:15px; font-weight:800; color:${isAbove ? '#15803d' : '#b45309'};">
            <span>${I18n.t("compare.variance_label", "Potential Revenue Difference")}:</span>
            <span>${c.gross_variance_value >= 0 ? '+' : ''}₹${c.gross_variance_value.toLocaleString("en-IN")}</span>
          </div>
        </div>

        <!-- Reference Mandi Details -->
        <div style="font-size:12px; color:#64748b; line-height:1.6; margin-bottom:16px; background:#f8fafc; padding:10px; border-radius:6px;">
          <div><strong>Reference Market</strong>: ${c.government_mandi_name}</div>
          <div><strong>Official Reporting Date</strong>: ${c.government_reporting_date} (${c.data_freshness})</div>
          <div>${c.formula_explanation}</div>
        </div>

        <!-- Official Disclaimer -->
        <div style="background:#fffbeb; border:1px solid #fef3c7; padding:12px; border-radius:6px; font-size:12px; color:#92400e; line-height:1.5;">
          <strong>${I18n.t("compare.disclaimer_title", "Important Official Disclaimer")}:</strong> ${c.disclaimer_text}
          <div style="margin-top:4px;">${c.is_msp_warning}</div>
        </div>
      </div>
    `;
  }
};

window.PriceCompare = PriceCompare;
