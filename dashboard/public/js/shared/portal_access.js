(function () {
    function el(id) {
        return document.getElementById(id);
    }

    function getClientName() {
        var input = el("clientDocname");
        return input ? input.value : "";
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    var PERMISSION_FIELDS = [
        "view_profile", "can_edit_profile", "can_view_appointments",
        "can_view_invoices", "can_pay_invoices", "can_view_courses_and_products",
        "can_view_downloads", "can_view_admin_details", "can_monitor_courses",
        "can_manage_staff_access", "can_view_sensitive_details",
    ];

    var editingRowName = null;
    var lastRows = [];

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
        var tableBody = el("portalAccessTableBody");
        if (!tableBody) return;

        var clientName = getClientName();
        if (!clientName) return;

        apiCall("get_portal_access_rows", { client_name: clientName }).then(function (data) {
            lastRows = (data && data.rows) || [];
            renderRelationshipOptions((data && data.relationship_options) || []);
            renderRows(lastRows, !!(data && data.can_manage));

            var addBtn = el("addPortalAccessBtn");
            if (addBtn) addBtn.style.display = (data && data.can_manage) ? "" : "none";
        }).catch(function () {
            tableBody.innerHTML = '<tr><td colspan="6" class="dashboard-empty">Unable to load portal access.</td></tr>';
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

    function renderRows(rows, canManage) {
        var tableBody = el("portalAccessTableBody");
        if (!tableBody) return;

        if (!rows.length) {
            tableBody.innerHTML = '<tr><td colspan="6" class="dashboard-empty">No portal access set up yet.</td></tr>';
            return;
        }

        tableBody.innerHTML = rows.map(function (row) {
            var actions = canManage
                ? '<button type="button" class="dashboard-link-btn portal-access-edit-btn" data-row="' + escapeHtml(row.name) + '">Edit</button> ' +
                  '<button type="button" class="dashboard-link-btn portal-access-remove-btn" data-row="' + escapeHtml(row.name) + '">Remove</button>'
                : "—";

            return (
                "<tr>" +
                "<td>" + escapeHtml(row.contact_name || "—") + "</td>" +
                "<td>" + escapeHtml(row.email_id || "—") + "</td>" +
                "<td>" + escapeHtml(row.relationship_type || "—") + "</td>" +
                "<td>" + (row.portal_access_enabled
                    ? '<span class="dashboard-badge dashboard-status-active">Enabled</span>'
                    : '<span class="dashboard-badge">Disabled</span>') + "</td>" +
                "<td>" + permissionSummary(row) + "</td>" +
                '<td class="dashboard-action-cell">' + actions + "</td>" +
                "</tr>"
            );
        }).join("");

        tableBody.querySelectorAll(".portal-access-edit-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                var row = lastRows.find(function (r) { return r.name === btn.dataset.row; });
                if (row) openForm(row);
            });
        });

        tableBody.querySelectorAll(".portal-access-remove-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (!window.confirm("Remove this person's portal access?")) return;

                apiCall("remove_portal_access_row", {
                    client_name: getClientName(),
                    row_name: btn.dataset.row,
                }).then(loadPortalAccess);
            });
        });
    }

    function openForm(row) {
        var panel = el("portalAccessFormPanel");
        if (!panel) return;

        editingRowName = (row && row.name) || null;

        el("portalAccessContactName").value = (row && row.contact_name) || "";
        el("portalAccessEmail").value = (row && row.email_id) || "";
        el("portalAccessPhone").value = (row && row.phone) || "";
        el("portalAccessRelationship").value = (row && row.relationship_type) || "";
        el("portalAccessIsPrimary").checked = !!(row && row.is_primary_contact);
        el("portalAccessIsBilling").checked = !!(row && row.is_billing_contact);
        el("portalAccessEnabled").checked = !!(row && row.portal_access_enabled);

        document.querySelectorAll(".portal-access-permission").forEach(function (checkbox) {
            checkbox.checked = !!(row && row[checkbox.dataset.field]);
        });

        var status = el("portalAccessFormStatus");
        if (status) status.textContent = "";

        panel.style.display = "block";
    }

    function closeForm() {
        var panel = el("portalAccessFormPanel");
        if (panel) panel.style.display = "none";
        editingRowName = null;
    }

    function saveForm() {
        var clientName = getClientName();
        var status = el("portalAccessFormStatus");

        var payload = {
            name: editingRowName,
            contact_name: el("portalAccessContactName").value,
            email_id: el("portalAccessEmail").value,
            phone: el("portalAccessPhone").value,
            relationship_type: el("portalAccessRelationship").value,
            is_primary_contact: el("portalAccessIsPrimary").checked ? 1 : 0,
            is_billing_contact: el("portalAccessIsBilling").checked ? 1 : 0,
            portal_access_enabled: el("portalAccessEnabled").checked ? 1 : 0,
        };

        document.querySelectorAll(".portal-access-permission").forEach(function (checkbox) {
            payload[checkbox.dataset.field] = checkbox.checked ? 1 : 0;
        });

        if (!payload.email_id) {
            if (status) status.textContent = "Email is required so this person can log in.";
            return;
        }

        apiCall("save_portal_access_row", {
            client_name: clientName,
            data: JSON.stringify(payload),
        }).then(function () {
            closeForm();
            loadPortalAccess();
        }).catch(function (r) {
            if (status) status.textContent = (r && r.message) || "Unable to save portal access.";
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!el("portalAccessTableBody")) return;

        loadPortalAccess();

        var addBtn = el("addPortalAccessBtn");
        if (addBtn) addBtn.addEventListener("click", function () { openForm(null); });

        var cancelBtn = el("cancelPortalAccess");
        if (cancelBtn) cancelBtn.addEventListener("click", closeForm);

        var saveBtn = el("savePortalAccess");
        if (saveBtn) saveBtn.addEventListener("click", saveForm);
    });
})();
