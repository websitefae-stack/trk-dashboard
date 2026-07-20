"""
Franchisor-only report: for a selected coach (or every coach), every
client's postcode(s) in one place, so a franchisor can see roughly where a
coach is working and plot it on a map. Two postcode sources are checked -
the client's own postcode field, and (if set) their Therapy Location's
postcode, since sessions may happen somewhere other than the client's home
address. Field names are resolved the same defensive "candidates" way
client_details.py's own address section does, since the live site's exact
Client field names aren't fixed by this repo's schema.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in, is_franchisor_user
from dashboard.api.shared.client_details import field_meta_lookup, find_field
from dashboard.api.shared.clients import get_coach_label, build_display_name

_POSTCODE_FIELD_CFG = {"label": "Zip Code", "candidates": ["zip_code", "postcode", "postal_code"]}
_THERAPY_LOCATION_FIELD_CFG = {"label": "Main Therapy Location", "candidates": ["main_therapy_location", "therapy_location"]}


def _client_field(field_cfg):
    meta = frappe.get_meta("Client")
    by_label, by_fieldname = field_meta_lookup(meta)
    df = find_field(field_cfg, by_label, by_fieldname)
    return df.fieldname if df else None


def _therapy_location_postcodes(location_names):
    if not location_names or not frappe.db.exists("DocType", "Therapy Location"):
        return {}

    if not frappe.get_meta("Therapy Location").has_field("postal_code"):
        return {}

    rows = frappe.get_all(
        "Therapy Location",
        filters={"name": ["in", list(location_names)]},
        fields=["name", "postal_code"],
        limit_page_length=5000,
        ignore_permissions=True,
    )

    return {row.name: (row.postal_code or "").strip() for row in rows if row.postal_code}


@frappe.whitelist()
def get_client_locations_report(coach=None):
    ensure_logged_in()

    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this report."), frappe.PermissionError)

    if not frappe.db.exists("DocType", "Client"):
        return []

    postcode_fieldname = _client_field(_POSTCODE_FIELD_CFG)
    therapy_location_fieldname = _client_field(_THERAPY_LOCATION_FIELD_CFG)

    fields = ["name", "primary_coach", "attending_coach"]
    if postcode_fieldname:
        fields.append(postcode_fieldname)
    if therapy_location_fieldname:
        fields.append(therapy_location_fieldname)

    client_meta = frappe.get_meta("Client")
    for candidate in ("full_name", "name1", "last_name", "preferred_name"):
        if client_meta.has_field(candidate) and candidate not in fields:
            fields.append(candidate)

    coach = (coach or "").strip()

    if coach:
        rows = frappe.get_all(
            "Client",
            fields=fields,
            or_filters={"primary_coach": coach, "attending_coach": coach},
            limit_page_length=5000,
            ignore_permissions=True,
        )
    else:
        rows = frappe.get_all(
            "Client",
            fields=fields,
            limit_page_length=5000,
            ignore_permissions=True,
        )

    therapy_location_names = {
        row.get(therapy_location_fieldname)
        for row in rows
        if therapy_location_fieldname and row.get(therapy_location_fieldname)
    }
    therapy_postcodes = _therapy_location_postcodes(therapy_location_names)

    out = []
    for row in rows:
        client_postcode = (row.get(postcode_fieldname) or "").strip() if postcode_fieldname else ""
        location_name = row.get(therapy_location_fieldname) if therapy_location_fieldname else None
        therapy_postcode = therapy_postcodes.get(location_name, "") if location_name else ""

        if not client_postcode and not therapy_postcode:
            continue

        coach_name = row.get("primary_coach") or row.get("attending_coach")

        out.append({
            "client": row.name,
            "client_label": build_display_name(row),
            "coach_label": get_coach_label(coach_name),
            "client_postcode": client_postcode,
            "therapy_postcode": therapy_postcode,
        })

    out.sort(key=lambda r: (r.get("client_label") or "").lower())

    return out
