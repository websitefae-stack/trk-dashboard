(function () {
    function el(id) {
        return document.getElementById(id);
    }

    function getClientName() {
        var input = el("clientDocname");
        return input ? input.value : "";
    }

    var PERMISSION_FIELDS = [
        "view_profile", "can_edit_profile", "can_view_appointments",
        "can_view_invoices", "can_pay_invoices", "can_view_courses_and_products",
        "can_view_downloads", "can_view_admin_details", "can_monitor_courses",
        "can_manage_staff_access", "can_view_sensitive_details",
    ];

    var rowsByContact = {};
    var currentContact = null;
    var currentRowName = null;

    function apiCall(method, args) {
        return new Promise(function (resolve, reject) {
            frappe.call({
                method: "dashboard.api.shared.portal_access." + method,
                args: args || {},
                callback: function (r) { resolve(r.message); },
                error: function (r) { reject(r); },
            });
        });
    }

    function loadPortalAccess() {
        var manageButtons = document.querySelectorAll(".portal-access-manage-btn");
        if (!manageButtons.length) return;

        var clientName = getClientName();
        if (!clientName) return;

        apiCall("get_portal_access_rows", { client_name: clientName }).then(function (data) {
            rowsByContact = {};
            ((data && data.rows) || []).forEach(function (row) {
                if (row.contact) rowsByContact[row.contact] = row;
            });

            renderRelationshipOptions((data && data.relationship_options) || []);
            renderStatuses(!!(data && data.can_manage));
        });
    }

    function renderRelationshipOptions(options) {
        var select = el("portalAccessRelationship");
        if (!select || select.dataset.populated) return;

        options.forEach(function (option) {
            var opt = document.createElement("option");
            opt.value = option;
            opt.textContent = option;
            select.appendChild(opt);
        });

        select.dataset.populated = "1";
    }

    function permissionSummary(row) {
        var count = PERMISSION_FIELDS.filter(function (field) { return row[field]; }).length;
        return count + " of " + PERMISSION_FIELDS.length;
    }

    function renderStatuses(canManage) {
        document.querySelectorAll(".portal-access-manage-btn").forEach(function (btn) {
            var contact = btn.dataset.contact;
            var row = contact ? rowsByContact[contact] : null;
            var statusEl = document.querySelector('.portal-access-status[data-contact="' + contact + '"]');

            if (statusEl) {
                if (row && row.portal_access_enabled) {
                    statusEl.innerHTML = '<span class="dashboard-badge dashboard-status-active">Enabled</span> <span class="dashboard-field-note">(' + permissionSummary(row) + ')</span>';
                } else if (row) {
                    statusEl.innerHTML = '<span class="dashboard-badge">Disabled</span>';
                } else {
                    statusEl.innerHTML = '<span class="dashboard-empty">No access</span>';
                }
            }

            btn.style.display = canManage ? "" : "none";
            btn.textContent = row ? "Manage" : "Grant Access";
        });
    }

    function openForm(button) {
        var panel = el("portalAccessFormPanel");
        if (!panel) return;

        currentContact = button.dataset.contact || "";
        var row = currentContact ? rowsByContact[currentContact] : null;
        currentRowName = (row && row.name) || null;

        var heading = el("portalAccessFormHeading");
        if (heading) {
            heading.textContent = "Managing portal access for " + (button.dataset.contactName || "this contact") +
                (button.dataset.email ? " (" + button.dataset.email + ")" : "");
        }

        el("portalAccessContactName").value = button.dataset.contactName || "";
        el("portalAccessEmail").value = button.dataset.email || "";
        el("portalAccessPhone").value = button.dataset.phone || "";
        el("portalAccessRelationship").value = (row && row.relationship_type) || button.dataset.relationship || "";
        el("portalAccessIsPrimary").checked = !!(row && row.is_primary_contact);
        el("portalAccessEnabled").checked = !!(row && row.portal_access_enabled);
        el("portalAccessNotify").checked = false;

        document.querySelectorAll(".portal-access-permission").forEach(function (checkbox) {
            checkbox.checked = !!(row && row[checkbox.dataset.field]);
        });

        var removeBtn = el("removePortalAccess");
        if (removeBtn) removeBtn.style.display = row ? "" : "none";

        var status = el("portalAccessFormStatus");
        if (status) status.textContent = "";

        panel.style.display = "block";
        panel.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    function closeForm() {
        var panel = el("portalAccessFormPanel");
        if (panel) panel.style.display = "none";
        currentContact = null;
        currentRowName = null;
    }

    function saveForm() {
        var clientName = getClientName();
        var status = el("portalAccessFormStatus");
        var manageBtn = currentContact
            ? document.querySelector('.portal-access-manage-btn[data-contact="' + currentContact + '"]')
            : null;

        var payload = {
            contact_name: el("portalAccessContactName").value,
            email_id: el("portalAccessEmail").value,
            phone: el("portalAccessPhone").value,
            relationship_type: el("portalAccessRelationship").value,
            is_primary_contact: el("portalAccessIsPrimary").checked ? 1 : 0,
            is_billing_contact: manageBtn && manageBtn.dataset.isBilling === "1" ? 1 : 0,
            portal_access_enabled: el("portalAccessEnabled").checked ? 1 : 0,
            notify_by_email: el("portalAccessNotify").checked ? 1 : 0,
        };

        document.querySelectorAll(".portal-access-permission").forEach(function (checkbox) {
            payload[checkbox.dataset.field] = checkbox.checked ? 1 : 0;
        });

        apiCall("save_portal_access_row", {
            client_name: clientName,
            contact: currentContact || "",
            data: JSON.stringify(payload),
        }).then(function () {
            closeForm();
            loadPortalAccess();
        }).catch(function (r) {
            if (status) status.textContent = (r && r.message) || "Unable to save portal access.";
        });
    }

    function removeAccess() {
        if (!currentRowName) return;
        if (!window.confirm("Remove this person's portal access? They will no longer be able to log in.")) return;

        apiCall("remove_portal_access_row", {
            client_name: getClientName(),
            row_name: currentRowName,
        }).then(function () {
            closeForm();
            loadPortalAccess();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!document.querySelector(".portal-access-manage-btn")) return;

        loadPortalAccess();

        document.body.addEventListener("click", function (e) {
            var btn = e.target.closest(".portal-access-manage-btn");
            if (btn) openForm(btn);
        });

        var cancelBtn = el("cancelPortalAccess");
        if (cancelBtn) cancelBtn.addEventListener("click", closeForm);

        var saveBtn = el("savePortalAccess");
        if (saveBtn) saveBtn.addEventListener("click", saveForm);

        var removeBtn = el("removePortalAccess");
        if (removeBtn) removeBtn.addEventListener("click", removeAccess);
    });
})();
