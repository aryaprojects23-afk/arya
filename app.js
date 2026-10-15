/**
 * HarvestLink 2.0 - Core Application Controller
 * Handles SPA view switching, demo persona management, farmer dashboard controls,
 * toast alerts, and localization auditing.
 */

const App = {
  currentView: "home",
  currentUser: null,

  async init() {
    await I18n.init();
    await this.initDemoUsers();
    this.bindGlobalNavigation();
    
    // Initialize components
    await MandiDashboard.init();
    await PriceCompare.init();
    await Marketplace.init();
    await this.loadCompletenessTable();

    // Check URL hash for routing
    const hash = window.location.hash.replace("#", "") || "home";
    this.switchView(hash);
  },

  async initDemoUsers() {
    try {
      const res = await fetch("/api/auth/demo-users");
      const data = await res.json();
      const sel = document.getElementById("demo-role-selector");
      if (sel) {
        sel.innerHTML = '<option value="">-- Switch Demo Role --</option>';
        data.demo_users.forEach(u => {
          const opt = document.createElement("option");
          opt.value = u.id;
          opt.textContent = `${u.full_name} (${u.role.toUpperCase()}) - ${u.district}`;
          if (u.id === "demo_farmer_ramesh") {
            opt.selected = true;
            this.currentUser = u;
          }
          sel.appendChild(opt);
        });

        sel.addEventListener("change", async (e) => {
          if (!e.target.value) return;
          const switchRes = await fetch(`/api/auth/switch-demo?user_id=${e.target.value}`, { method: "POST" });
          const userObj = await switchRes.json();
          this.currentUser = userObj.user;
          this.updateUserContext();
          App.showToast(`Switched to: ${this.currentUser.full_name} (${this.currentUser.role})`, "info");
          if (this.currentView === "farmer_dashboard") {
            FarmerDashboard.loadFarmerDashboard();
          }
        });
      }
      this.updateUserContext();
    } catch (e) {
      console.error("Error initializing demo personas:", e);
    }
  },

  updateUserContext() {
    const badge = document.getElementById("active-user-badge");
    if (badge && this.currentUser) {
      badge.innerHTML = `<strong>👤 ${this.currentUser.full_name}</strong> <span style="font-size:11px; background:#e2e8f0; padding:2px 6px; border-radius:4px;">${this.currentUser.role.toUpperCase()}</span>`;
    }
  },

  bindGlobalNavigation() {
    document.querySelectorAll("[data-nav-view]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const view = btn.getAttribute("data-nav-view");
        this.switchView(view);
      });
    });

    // Translation report form
    const reportForm = document.getElementById("form-report-translation");
    if (reportForm) {
      reportForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
          language_code: I18n.currentLanguage,
          translation_key: document.getElementById("report-key-input")?.value || "General Term",
          current_text: document.getElementById("report-current-input")?.value || "",
          suggested_correction: document.getElementById("report-suggested-input")?.value || "",
          user_notes: document.getElementById("report-notes-input")?.value || ""
        };

        try {
          const res = await fetch("/api/i18n/report-translation", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
          });
          const resData = await res.json();
          App.showToast(resData.message || "Thank you! Suggestion recorded.", "success");
          document.getElementById("report-modal")?.classList.remove("active");
          reportForm.reset();
        } catch (err) {
          App.showToast("Failed to submit suggestion.", "danger");
        }
      });
    }

    // Modal close triggers
    document.querySelectorAll(".modal-close-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".modal-overlay").forEach(m => m.classList.remove("active"));
      });
    });
  },

  switchView(viewId) {
    this.currentView = viewId;
    window.location.hash = viewId;

    // Toggle view sections
    document.querySelectorAll(".view-section").forEach(sec => {
      sec.classList.remove("active");
    });
    const targetSection = document.getElementById(`view-${viewId}`);
    if (targetSection) {
      targetSection.classList.add("active");
    }

    // Toggle active state on nav links
    document.querySelectorAll("[data-nav-view]").forEach(link => {
      if (link.getAttribute("data-nav-view") === viewId) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });

    window.scrollTo({ top: 0, behavior: "smooth" });

    // View specific hooks
    if (viewId === "farmer_dashboard") {
      FarmerDashboard.loadFarmerDashboard();
    } else if (viewId === "completeness") {
      this.loadCompletenessTable();
    } else if (viewId === "cart") {
      Marketplace.renderCartView();
    }
  },

  async loadCompletenessTable() {
    const tbody = document.getElementById("completeness-table-body");
    if (!tbody) return;

    try {
      const res = await fetch("/api/i18n/completeness");
      const data = await res.json();
      const langs = data.languages || [];

      tbody.innerHTML = "";
      langs.forEach(l => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${l.code}</strong></td>
          <td>${l.name}</td>
          <td style="font-size:16px;"><strong>${l.native}</strong></td>
          <td>${l.script}</td>
          <td><span class="badge ${l.direction === 'rtl' ? 'badge-stale' : 'badge-verified'}">${l.direction.toUpperCase()}</span></td>
          <td>${l.total_keys}</td>
          <td><strong style="color:#15803d;">${l.translated_keys}</strong></td>
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <div style="flex:1; height:8px; background:#e2e8f0; border-radius:4px; overflow:hidden;">
                <div style="width:${l.coverage_percentage}%; height:100%; background:var(--primary);"></div>
              </div>
              <strong style="font-size:12px;">${l.coverage_percentage}%</strong>
            </div>
          </td>
          <td><span class="badge badge-live">${l.status}</span></td>
        `;
        tbody.appendChild(tr);
      });
    } catch (e) {
      console.error("Failed to load completeness table:", e);
    }
  },

  showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style = "position:fixed; top:20px; right:20px; z-index:9999; display:flex; flex-direction:column; gap:8px;";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    const bg = type === "success" ? "#15803d" : (type === "warning" ? "#b45309" : (type === "danger" ? "#b91c1c" : "#1e293b"));
    toast.style = `background:${bg}; color:#ffffff; padding:12px 18px; border-radius:8px; font-size:14px; font-weight:600; box-shadow:0 4px 6px rgba(0,0,0,0.15); transition:opacity 0.3s ease;`;
    toast.textContent = message;

    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
};

const FarmerDashboard = {
  async loadFarmerDashboard() {
    const statsContainer = document.getElementById("farmer-stats-grid");
    const listingsTbody = document.getElementById("farmer-listings-table-body");
    const farmerId = App.currentUser?.id || "demo_farmer_ramesh";

    try {
      // 1. Fetch KPIs
      const statsRes = await fetch(`/api/farmer/stats`, {
        headers: { "Authorization": `Bearer ${localStorage.getItem("harvestlink_token") || ''}` }
      });
      const stats = await statsRes.json();

      if (statsContainer) {
        statsContainer.innerHTML = `
          <div class="card" style="margin-bottom:0; text-align:center;">
            <div style="font-size:13px; color:#64748b; font-weight:600;">ACTIVE PRODUCE LISTINGS</div>
            <div style="font-size:28px; font-weight:800; color:var(--primary-dark);">${stats.active_listings}</div>
          </div>
          <div class="card" style="margin-bottom:0; text-align:center;">
            <div style="font-size:13px; color:#64748b; font-weight:600;">TOTAL FARM SALES</div>
            <div style="font-size:28px; font-weight:800; color:#15803d;">₹${stats.total_sales.toLocaleString("en-IN")}</div>
          </div>
          <div class="card" style="margin-bottom:0; text-align:center;">
            <div style="font-size:13px; color:#64748b; font-weight:600;">PENDING ORDERS</div>
            <div style="font-size:28px; font-weight:800; color:#d97706;">${stats.pending_orders}</div>
          </div>
          <div class="card" style="margin-bottom:0; text-align:center;">
            <div style="font-size:13px; color:#64748b; font-weight:600;">WHOLESALE QUOTES</div>
            <div style="font-size:28px; font-weight:800; color:#0369a1;">${stats.pending_quotes}</div>
          </div>
        `;
      }

      // 2. Fetch Farmer Listings
      const prodsRes = await fetch(`/api/products?farmer_id=${farmerId}`);
      const prodsData = await prodsRes.json();
      const myProds = prodsData.products || [];

      if (listingsTbody) {
        if (myProds.length === 0) {
          listingsTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:#64748b;">No active listings yet. Click "Add New Produce Listing" above!</td></tr>`;
          return;
        }

        listingsTbody.innerHTML = "";
        myProds.forEach(p => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${p.title}</strong><br><small style="color:#64748b;">${p.variety} (${p.grade})</small></td>
            <td><strong>₹${p.price_per_unit}</strong> / ${p.unit}</td>
            <td>${p.available_quantity} ${p.unit}</td>
            <td>${p.mandi_reference_price_per_kg ? '₹' + p.mandi_reference_price_per_kg + '/kg' : '—'}</td>
            <td><span class="badge badge-live">${p.status.toUpperCase()}</span></td>
            <td>
              <button class="btn btn-light btn-sm" onclick="App.showToast('Listing settings updated', 'info')">Manage</button>
            </td>
          `;
          listingsTbody.appendChild(tr);
        });
      }

    } catch (e) {
      console.error("Failed to load farmer dashboard:", e);
    }
  }
};

window.App = App;
window.FarmerDashboard = FarmerDashboard;

document.addEventListener("DOMContentLoaded", () => {
  App.init();
});
