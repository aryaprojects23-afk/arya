/**
 * HarvestLink 2.0 - Client-Side Internationalization Engine
 * Supports 22 Indian languages, instant language switching, state preservation,
 * and RTL layout toggling for Urdu and Kashmiri.
 */

const I18n = {
  currentLanguage: localStorage.getItem("harvestlink_lang") || "en",
  currentDirection: "ltr",
  translations: {},
  languages: [],

  async init() {
    await this.fetchLanguageList();
    await this.loadLanguage(this.currentLanguage);
    this.setupLanguageSelectors();
  },

  async fetchLanguageList() {
    try {
      const res = await fetch("/api/i18n/languages");
      const data = await res.json();
      this.languages = data.languages;
    } catch (e) {
      console.error("Failed to load languages list:", e);
    }
  },

  async loadLanguage(langCode) {
    try {
      const res = await fetch(`/api/i18n/locales/${langCode}`);
      const data = await res.json();
      this.currentLanguage = data.language_code || langCode;
      this.currentDirection = data.direction || "ltr";
      this.translations = data.translations || {};

      localStorage.setItem("harvestlink_lang", this.currentLanguage);
      document.documentElement.lang = this.currentLanguage;
      document.documentElement.dir = this.currentDirection;

      // Update stylesheet link or class for RTL
      const rtlLink = document.getElementById("rtl-stylesheet");
      if (rtlLink) {
        rtlLink.disabled = (this.currentDirection !== "rtl");
      }

      // Synchronize all select elements
      document.querySelectorAll(".lang-select").forEach(sel => {
        sel.value = this.currentLanguage;
      });

      // Update all translated elements in DOM
      this.translateDOM();

      // Dispatch language change event for other components (mandi, compare, marketplace)
      window.dispatchEvent(new CustomEvent("harvestlink:languageChanged", {
        detail: { language: this.currentLanguage, direction: this.currentDirection }
      }));

      // Optionally notify backend profile
      const token = localStorage.getItem("harvestlink_token");
      if (token) {
        fetch("/api/user/language", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
          body: JSON.stringify({ preferred_language: this.currentLanguage })
        }).catch(() => {});
      }

    } catch (e) {
      console.error(`Failed to load locale '${langCode}':`, e);
    }
  },

  translateDOM(container = document) {
    // 1. Text Content
    container.querySelectorAll("[data-i18n]").forEach(el => {
      const key = el.getAttribute("data-i18n");
      const val = this.resolveKey(key);
      if (val !== undefined && val !== null && val !== "") {
        el.textContent = val;
      }
    });

    // 2. Placeholders
    container.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
      const key = el.getAttribute("data-i18n-placeholder");
      const val = this.resolveKey(key);
      if (val) {
        el.setAttribute("placeholder", val);
      }
    });

    // 3. Titles / Tooltips
    container.querySelectorAll("[data-i18n-title]").forEach(el => {
      const key = el.getAttribute("data-i18n-title");
      const val = this.resolveKey(key);
      if (val) {
        el.setAttribute("title", val);
      }
    });
  },

  resolveKey(path) {
    if (!path) return "";
    const parts = path.split(".");
    let curr = this.translations;
    for (const p of parts) {
      if (curr && typeof curr === "object" && p in curr) {
        curr = curr[p];
      } else {
        return null;
      }
    }
    return curr;
  },

  t(path, fallback = "") {
    const val = this.resolveKey(path);
    return val !== null && val !== undefined ? val : fallback;
  },

  setupLanguageSelectors() {
    const selectors = document.querySelectorAll(".lang-select");
    selectors.forEach(sel => {
      sel.innerHTML = "";
      this.languages.forEach(l => {
        const opt = document.createElement("option");
        opt.value = l.code;
        opt.textContent = `${l.native} (${l.name})`;
        if (l.code === this.currentLanguage) {
          opt.selected = true;
        }
        sel.appendChild(opt);
      });

      sel.addEventListener("change", (e) => {
        this.loadLanguage(e.target.value);
      });
    });
  }
};

window.I18n = I18n;
