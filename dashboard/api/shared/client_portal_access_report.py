"""
"Reports > Client Portal Access" - a flat, role-scoped list of every
client the current user can already see, showing whether anyone on
that client has portal access yet and when it was granted. Only the
franchisor and a client's own primary coach can actually grant access
(portal_access.py's own gate, unchanged - see save_portal_access_row/
_ensure_can_manage_portal_access); an attending coach or session
worker sees the same status here but gets pointed at who to ask
instead of a working button, per Ashley's own instruction.

The per-client detail (every contact, their individual status, grant/
notify dates) reuses portal_access.get_portal_access_rows() directly -
no separate read endpoint needed for that.
"""

import frappe

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_allowed_client_names,
    get_current_user_dashboard_type,
    get_current_coach_name,
)
from dashboard.api.shared.clients import get_coach_label, build_display_name

CLIENT_DOCTYPE = "Client"
LINK_DOCTYPE = "Client Contact Link"


@frappe.whitelist()
def get_client_portal_access_report():
    ensure_logged_in()

    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return {"rows": []}

    client_names = get_allowed_client_names()
    if not client_names:
        return {"rows": []}

    client_meta = frappe.get_meta(CLIENT_DOCTYPE)
    fields = ["name", "primary_coach", "attending_coach"]

    for candidate in ("full_name", "name1", "first_name", "last_name", "preferred_name"):
        if client_meta.has_field(candidate) and candidate not in fields:
            fields.append(candidate)

    clients = frappe.get_all(
        CLIENT_DOCTYPE,
        filters={"name": ["in", client_names]},
        fields=fields,
        limit_page_length=5000,
        ignore_permissions=True,
    )

    link_rows_by_client = {}

    if frappe.db.exists("DocType", LINK_DOCTYPE):
        link_meta = frappe.get_meta(LINK_DOCTYPE)
        link_fields = ["parent", "portal_access_enabled"]

        if link_meta.has_field("portal_access_granted_on"):
            link_fields.append("portal_access_granted_on")

        for row in frappe.get_all(
            LINK_DOCTYPE,
            filters={"parenttype": CLIENT_DOCTYPE, "parent": ["in", [c.name for c in clients]]},
            fields=link_fields,
        ):
            link_rows_by_client.setdefault(row.parent, []).append(row)

    dashboard_type = get_current_user_dashboard_type()
    own_coach_name = get_current_coach_name(optional=True) if dashboard_type == "coach" else None
    viewer_is_franchisor = is_franchisor_user()

    out = []
    for client in clients:
        links = link_rows_by_client.get(client.name, [])
        enabled_links = [row for row in links if row.get("portal_access_enabled")]

        granted_dates = [
            row.get("portal_access_granted_on") for row in enabled_links
            if row.get("portal_access_granted_on")
        ]

        primary_coach = client.get("primary_coach")

        can_manage = bool(
            viewer_is_franchisor
            or (dashboard_type == "coach" and own_coach_name and own_coach_name == primary_coach)
        )

        out.append({
            "client": client.name,
            "client_label": build_display_name(client),
            "primary_coach_label": get_coach_label(primary_coach) if primary_coach else "",
            "has_access": bool(enabled_links),
            "granted_on": max(granted_dates) if granted_dates else "",
            "contact_count": len(links),
            "can_manage": can_manage,
        })

    out.sort(key=lambda row: (row.get("client_label") or "").lower())

    return {"rows": out}
