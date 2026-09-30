/**
 * Store dashboard's Shipping settings page (see dashboard.api.shared.
 * store_shipping) - the five weight-band rates charged on a physical
 * Store order, plus the on/off switch.
 */
(function () {
  "use strict";

  const API = "dashboard.api.shared.store_shipping";

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : "";
  }

  async function apiPost(method, args) {
    const response = await fetch(`/api/method/${method}`, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": getCsrfToken(),
      },
      body: JSON.stringify(args || {}),
    });

    const data = await response.json();

    if (!response.ok || data.exc) {
      throw new Error(data.message || "There was a problem loading this.");
    }

    return data.message;
  }

  const FIELDS = [
    "rate_under_1kg",
    "rate_under_2kg",
    "rate_under_3kg",
    "rate_under_4kg",
    "rate_under_5kg",
    "rate_over_5kg",
  ];

  const FIELD_TO_INPUT_ID = {
    rate_under_1kg: "rateUnder1kg",
    rate_under_2kg: "rateUnder2kg",
    rate_under_3kg: "rateUnder3kg",
    rate_under_4kg: "rateUnder4kg",
    rate_under_5kg: "rateUnder5kg",
    rate_over_5kg: "rateOver5kg",
  };

  async function loadSettings() {
    const settings = await apiPost(`${API}.get_shipping_settings_for_ui`);

    document.getElementById("shippingEnabled").checked = !!settings.shipping_enabled;

    FIELDS.forEach((field) => {
      const input = document.getElementById(FIELD_TO_INPUT_ID[field]);
      if (input) input.value = settings[field] || "";
    });
  }

  async function saveSettings() {
    const btn = document.getElementById("saveShippingSettingsBtn");
    const note = document.getElementById("shippingSettingsSavedNote");

    btn.disabled = true;
    note.style.display = "none";

    try {
      const args = {
        shipping_enabled: document.getElementById("shippingEnabled").checked ? 1 : 0,
      };

      FIELDS.forEach((field) => {
        const input = document.getElementById(FIELD_TO_INPUT_ID[field]);
        args[field] = input ? input.value : 0;
      });

      await apiPost(`${API}.save_shipping_settings`, args);

      note.style.display = "inline";
    } catch (err) {
      alert(err.message || "Could not save shipping rates.");
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById("storeShippingPage")) return;

    loadSettings().catch((err) => {
      alert(err.message || "Could not load shipping settings.");
    });

    document.getElementById("saveShippingSettingsBtn").addEventListener("click", saveSettings);
  });
})();
