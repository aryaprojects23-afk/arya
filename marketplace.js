/**
 * HarvestLink 2.0 - Direct Farmer-to-Buyer Marketplace Module
 * Handles produce discovery, smart localized search, shopping cart, checkout,
 * order tracking milestones, and farmer inventory dashboards.
 */

const Marketplace = {
  cart: JSON.parse(localStorage.getItem("harvestlink_cart") || "[]"),
  currentCategory: "all",
  currentSearch: "",

  async init() {
    this.updateCartBadge();
    this.bindEvents();
    await this.fetchAndRenderProducts();
  },

  bindEvents() {
    // Search input with autocomplete
    const searchInput = document.getElementById("market-search-input");
    const autoBox = document.getElementById("search-autocomplete-box");

    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value.trim();
        this.currentSearch = query;

        debounceTimer = setTimeout(async () => {
          this.fetchAndRenderProducts();
          if (query.length >= 2 && autoBox) {
            try {
              const res = await fetch(`/api/commodities/autocomplete?q=${encodeURIComponent(query)}&lang=${I18n.currentLanguage}`);
              const data = await res.json();
              if (data.suggestions && data.suggestions.length > 0) {
                autoBox.innerHTML = data.suggestions.map(s => `
                  <div class="autocomplete-item" data-term="${s.term}" style="padding:8px 12px; cursor:pointer; border-bottom:1px solid #f1f5f9;">
                    <strong>${s.term}</strong> <span style="font-size:12px; color:#64748b;">→ ${s.canonical_name} (${s.localized_name})</span>
                  </div>
                `).join("");
                autoBox.style.display = "block";

                autoBox.querySelectorAll(".autocomplete-item").forEach(item => {
                  item.addEventListener("click", () => {
                    searchInput.value = item.getAttribute("data-term");
                    this.currentSearch = searchInput.value;
                    autoBox.style.display = "none";
                    this.fetchAndRenderProducts();
                  });
                });
              } else {
                autoBox.style.display = "none";
              }
            } catch (err) {}
          } else if (autoBox) {
            autoBox.style.display = "none";
          }
        }, 300);
      });
    }

    // Category pills
    document.querySelectorAll(".category-pill").forEach(pill => {
      pill.addEventListener("click", (e) => {
        document.querySelectorAll(".category-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        this.currentCategory = pill.getAttribute("data-category");
        this.fetchAndRenderProducts();
      });
    });

    // Cart pill click -> Open Cart View
    const cartBtn = document.getElementById("btn-header-cart");
    if (cartBtn) {
      cartBtn.addEventListener("click", () => {
        App.switchView("cart");
        this.renderCartView();
      });
    }

    // Add Produce Listing Form Submission
    const addListingForm = document.getElementById("form-add-listing");
    if (addListingForm) {
      addListingForm.addEventListener("submit", (e) => this.handleCreateListing(e));
    }

    // Checkout form submission
    const checkoutForm = document.getElementById("form-checkout");
    if (checkoutForm) {
      checkoutForm.addEventListener("submit", (e) => this.handlePlaceOrder(e));
    }
  },

  async fetchAndRenderProducts() {
    const grid = document.getElementById("produce-cards-grid");
    if (!grid) return;

    grid.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:40px; color:#64748b;">${I18n.t("common.loading", "Loading fresh farm produce...")}</div>`;

    try {
      const params = new URLSearchParams();
      if (this.currentCategory && this.currentCategory !== "all") params.append("category", this.currentCategory);
      if (this.currentSearch) params.append("search", this.currentSearch);

      const res = await fetch(`/api/products?${params.toString()}`);
      const data = await res.json();
      const products = data.products || [];

      if (products.length === 0) {
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align:center; padding: 40px; background:#ffffff; border-radius:12px; border:1px solid #e2e8f0;">
            <div style="font-size:32px; margin-bottom:8px;">🌾</div>
            <h3>No produce listings found</h3>
            <p style="color:#64748b;">Try searching for other crops or clearing category filters.</p>
          </div>
        `;
        return;
      }

      grid.innerHTML = "";
      products.forEach(p => {
        const card = document.createElement("div");
        card.className = "produce-card";
        
        const mandiNotice = p.mandi_reference_price_per_kg 
          ? `<div class="mandi-ref-box">⚖️ Govt Mandi Ref: <strong>₹${p.mandi_reference_price_per_kg}/kg</strong></div>`
          : "";

        card.innerHTML = `
          <img src="${p.image_url || 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=600'}" alt="${p.title}" class="produce-img">
          <div class="produce-body">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
              <span class="badge ${p.organic_certified ? 'badge-live' : 'badge-verified'}">${p.organic_certified ? '🌱 Organic' : p.grade}</span>
              <span style="font-size:12px; color:#64748b;">${p.location_district}, ${p.location_state}</span>
            </div>
            
            <h3 class="produce-title">${p.title}</h3>
            <div class="produce-farmer">👨‍🌾 ${p.farmer_name}</div>
            
            <div class="price-display">
              <span class="price-val">₹${p.price_per_unit}</span>
              <span class="price-unit">/ ${p.unit}</span>
            </div>

            ${mandiNotice}

            <div style="font-size:12px; color:#475569; margin-bottom:14px; line-height:1.5;">
              <div>Available: <strong>${p.available_quantity} ${p.unit}</strong> | Min Order: <strong>${p.minimum_order_qty} ${p.unit}</strong></div>
              ${p.bulk_discount_percentage > 0 ? `<div style="color:#b45309;">Bulk: ${p.bulk_discount_percentage}% off for ≥${p.bulk_threshold_qty} ${p.unit}</div>` : ''}
            </div>

            <div style="margin-top:auto; display:flex; gap:8px;">
              <button class="btn btn-primary btn-sm btn-add-cart" data-id="${p.id}" style="flex:1;">
                🛒 ${I18n.t("marketplace.btn_add_to_cart", "Add to Cart")}
              </button>
              <button class="btn btn-light btn-sm btn-quote" data-id="${p.id}" data-farmer="${p.farmer_id}" data-crop="${p.commodity_id}" title="Request Wholesale Quote">
                💼 Quote
              </button>
            </div>
          </div>
        `;

        card.querySelector(".btn-add-cart").addEventListener("click", () => this.addToCart(p));
        card.querySelector(".btn-quote").addEventListener("click", () => this.openQuoteModal(p));

        grid.appendChild(card);
      });

    } catch (e) {
      console.error("Failed to load products:", e);
    }
  },

  addToCart(product) {
    const existing = this.cart.find(it => it.product_id === product.id);
    if (existing) {
      existing.quantity += product.minimum_order_qty || 1;
    } else {
      this.cart.push({
        product_id: product.id,
        title: product.title,
        price_per_unit: product.price_per_unit,
        unit: product.unit,
        farmer_name: product.farmer_name,
        quantity: product.minimum_order_qty || 1,
        bulk_discount: product.bulk_discount_percentage || 0,
        bulk_threshold: product.bulk_threshold_qty || 0
      });
    }

    localStorage.setItem("harvestlink_cart", JSON.stringify(this.cart));
    this.updateCartBadge();
    App.showToast(`Added ${product.title} to your cart.`, "success");
  },

  updateCartBadge() {
    const badge = document.getElementById("header-cart-count");
    if (badge) {
      const totalItems = this.cart.reduce((sum, it) => sum + 1, 0);
      badge.textContent = totalItems;
      badge.style.display = totalItems > 0 ? "inline-block" : "none";
    }
  },

  renderCartView() {
    const container = document.getElementById("cart-items-list");
    const subtotalEl = document.getElementById("cart-subtotal");
    const totalEl = document.getElementById("cart-total");
    if (!container) return;

    if (this.cart.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:40px; background:#ffffff; border-radius:12px; border:1px solid #e2e8f0;">
          <div style="font-size:36px; margin-bottom:10px;">🛒</div>
          <h3>${I18n.t("cart.empty_message", "Your cart is currently empty.")}</h3>
          <button class="btn btn-primary" style="margin-top:14px;" onclick="App.switchView('marketplace')">
            Explore Farm Produce
          </button>
        </div>
      `;
      if (subtotalEl) subtotalEl.textContent = "₹0";
      if (totalEl) totalEl.textContent = "₹0";
      return;
    }

    let subtotal = 0;
    container.innerHTML = "";

    this.cart.forEach((it, idx) => {
      let unitPrice = it.price_per_unit;
      if (it.bulk_discount > 0 && it.quantity >= it.bulk_threshold > 0) {
        unitPrice -= (it.bulk_discount / 100.0) * unitPrice;
      }
      const lineTotal = unitPrice * it.quantity;
      subtotal += lineTotal;

      const row = document.createElement("div");
      row.style = "background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;";
      row.innerHTML = `
        <div>
          <div style="font-weight:700; font-size:16px; color:var(--primary-dark);">${it.title}</div>
          <div style="font-size:13px; color:#64748b;">Farmer: ${it.farmer_name} | ₹${it.price_per_unit}/${it.unit}</div>
        </div>

        <div style="display:flex; align-items:center; gap:12px;">
          <div style="display:flex; align-items:center; border:1.5px solid #cbd5e1; border-radius:6px; overflow:hidden;">
            <button class="btn-qty-minus" style="padding:6px 12px; background:#f1f5f9; border:none; cursor:pointer; font-weight:bold;">-</button>
            <span style="padding:6px 14px; font-weight:700; min-width:40px; text-align:center;">${it.quantity} ${it.unit}</span>
            <button class="btn-qty-plus" style="padding:6px 12px; background:#f1f5f9; border:none; cursor:pointer; font-weight:bold;">+</button>
          </div>

          <div style="font-weight:800; font-size:18px; color:var(--primary-dark); min-width:80px; text-align:right;">
            ₹${lineTotal.toFixed(2)}
          </div>

          <button class="btn-remove-item" style="background:none; border:none; color:#ef4444; cursor:pointer; font-size:16px;">✕</button>
        </div>
      `;

      row.querySelector(".btn-qty-minus").addEventListener("click", () => {
        if (it.quantity > 1) {
          it.quantity -= 1;
        } else {
          this.cart.splice(idx, 1);
        }
        localStorage.setItem("harvestlink_cart", JSON.stringify(this.cart));
        this.updateCartBadge();
        this.renderCartView();
      });

      row.querySelector(".btn-qty-plus").addEventListener("click", () => {
        it.quantity += 1;
        localStorage.setItem("harvestlink_cart", JSON.stringify(this.cart));
        this.updateCartBadge();
        this.renderCartView();
      });

      row.querySelector(".btn-remove-item").addEventListener("click", () => {
        this.cart.splice(idx, 1);
        localStorage.setItem("harvestlink_cart", JSON.stringify(this.cart));
        this.updateCartBadge();
        this.renderCartView();
      });

      container.appendChild(row);
    });

    if (subtotalEl) subtotalEl.textContent = `₹${subtotal.toLocaleString("en-IN")}`;
    if (totalEl) totalEl.textContent = `₹${subtotal.toLocaleString("en-IN")}`;
  },

  async handlePlaceOrder(e) {
    e.preventDefault();
    if (this.cart.length === 0) {
      App.showToast("Your cart is empty.", "warning");
      return;
    }

    const payload = {
      items: this.cart.map(it => ({ product_id: it.product_id, quantity: it.quantity })),
      delivery_address: document.getElementById("order-address")?.value || "MG Road, Suite 4B",
      delivery_district: document.getElementById("order-district")?.value || "Chittoor",
      delivery_state: document.getElementById("order-state")?.value || "Andhra Pradesh",
      delivery_pincode: document.getElementById("order-pincode")?.value || "517001",
      contact_phone: document.getElementById("order-phone")?.value || "9876543210",
      payment_method: document.getElementById("order-payment-method")?.value || "cash_on_delivery"
    };

    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Order submission failed.");
      }

      const orderData = await res.json();
      this.cart = [];
      localStorage.removeItem("harvestlink_cart");
      this.updateCartBadge();

      App.showToast(`Order #${orderData.order.order_number} successfully placed!`, "success");
      this.showOrderConfirmation(orderData.order);

    } catch (e) {
      App.showToast(e.message, "danger");
    }
  },

  showOrderConfirmation(order) {
    const container = document.getElementById("cart-view-container");
    if (!container) return;
    
    container.innerHTML = `
      <div style="background:#ffffff; border:2px solid #86efac; border-radius:12px; padding:32px; text-align:center;">
        <div style="font-size:48px; margin-bottom:12px;">🎉</div>
        <h2 style="color:var(--primary-dark); margin-bottom:8px;">Direct Farm Order Confirmed!</h2>
        <div style="font-size:18px; font-weight:800; color:#15803d; margin-bottom:14px;">${order.order_number}</div>
        <p style="color:#475569; max-width:600px; margin:0 auto 20px auto;">
          Your order has been directly transmitted to the farmer. You can track transit milestones in real time below.
        </p>

        <!-- Order Milestone Tracker -->
        <div style="display:flex; justify-content:center; gap:8px; margin-bottom:28px; flex-wrap:wrap;">
          <span class="badge badge-verified">1. Accepted by Farmer</span>
          <span class="badge" style="background:#f1f5f9; color:#64748b;">2. Packed at Farm</span>
          <span class="badge" style="background:#f1f5f9; color:#64748b;">3. Dispatched</span>
          <span class="badge" style="background:#f1f5f9; color:#64748b;">4. Out for Delivery</span>
        </div>

        <div style="display:flex; gap:12px; justify-content:center;">
          <button class="btn btn-primary" onclick="App.switchView('marketplace')">Continue Trading</button>
          <button class="btn btn-light" onclick="FarmerDashboard.loadFarmerDashboard()">View In Orders</button>
        </div>
      </div>
    `;
  },

  openQuoteModal(product) {
    const modal = document.getElementById("quote-modal");
    if (!modal) return;
    document.getElementById("quote-farmer-id").value = product.farmer_id;
    document.getElementById("quote-commodity-id").value = product.commodity_id;
    document.getElementById("quote-produce-title").textContent = product.title;
    modal.classList.add("active");
  }
};

window.Marketplace = Marketplace;
