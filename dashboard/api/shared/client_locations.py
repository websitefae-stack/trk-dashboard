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
from dashboard.api.shared.postcode_boundaries import get_territory_features

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


def _outward_code(postcode):
    """
    The "outward" half of a UK postcode (e.g. "N1" from "N1 2AB", "SW1A"
    from "SW1A 1AA") - the inward half is always exactly 3 characters
    (digit + 2 letters), so stripping the last 3 characters works whether
    or not the postcode has a space in it.
    """
    postcode = (postcode or "").strip().upper().replace(" ", "")
    if len(postcode) <= 3:
        return postcode
    return postcode[:-3]


def _get_coach_territories():
    """{coach_name: [prefix, ...]} for every coach with Territory Postcode
    Areas set (a Custom Field - see add_coach_territory_postcodes_field.py
    patch) - empty until office has actually filled any in."""
    if not frappe.get_meta("Coach").has_field("territory_postcodes"):
        return {}

    rows = frappe.get_all(
        "Coach",
        filters={"territory_postcodes": ["is", "set"]},
        fields=["name", "territory_postcodes"],
        limit_page_length=1000,
        ignore_permissions=True,
    )

    territories = {}
    for row in rows:
        prefixes = [p.strip().upper() for p in (row.territory_postcodes or "").split(",") if p.strip()]
        if prefixes:
            territories[row.name] = prefixes

    return territories


def _area_check(coach_name, postcodes, territories):
    """
    None: no territory defined for this client's own coach, so there's
    nothing to check against. True: at least one of the client's postcodes
    falls inside their own coach's territory. False: none do - `other`
    names whichever other coach's territory one of them falls into
    instead, if any.
    """
    own_prefixes = territories.get(coach_name)
    postcodes = [p for p in postcodes if p]

    if not own_prefixes or not postcodes:
        return None, ""

    outward_codes = [_outward_code(p) for p in postcodes]

    if any(code.startswith(prefix) for code in outward_codes for prefix in own_prefixes):
        return True, ""

    for other_coach, other_prefixes in territories.items():
        if other_coach == coach_name:
            continue
        if any(code.startswith(prefix) for code in outward_codes for prefix in other_prefixes):
            return False, get_coach_label(other_coach)

    return False, ""


@frappe.whitelist()
def get_client_locations_report(coach=None):
    ensure_logged_in()

    if not is_franchisor_user():
        frappe.throw(_("You do not have permission to view this report."), frappe.PermissionError)

    if not frappe.db.exists("DocType", "Client"):
        return {"rows": [], "territories": {}}

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
    territories = _get_coach_territories()

    out = []
    for row in rows:
        client_postcode = (row.get(postcode_fieldname) or "").strip() if postcode_fieldname else ""
        location_name = row.get(therapy_location_fieldname) if therapy_location_fieldname else None
        therapy_postcode = therapy_postcodes.get(location_name, "") if location_name else ""

        if not client_postcode and not therapy_postcode:
            continue

        coach_name = row.get("primary_coach") or row.get("attending_coach")
        in_area, other_coach_label = _area_check(coach_name, [client_postcode, therapy_postcode], territories)

        out.append({
            "client": row.name,
            "client_label": build_display_name(row),
            "coach": coach_name,
            "coach_label": get_coach_label(coach_name),
            "client_postcode": client_postcode,
            "therapy_postcode": therapy_postcode,
            "in_area": in_area,
            "other_coach_label": other_coach_label,
        })

    out.sort(key=lambda r: (r.get("client_label") or "").lower())

    territory_boundaries = {
        coach_name: get_territory_features(prefixes)
        for coach_name, prefixes in territories.items()
    }

    territory_overlaps = _get_territory_overlaps(territory_boundaries)

    return {
        "rows": out,
        "territories": territories,
        "territory_boundaries": territory_boundaries,
        "territory_overlaps": territory_overlaps,
    }


def _get_territory_overlaps(territory_boundaries):
    """
    Real postcode-shaped boundaries (unlike the old Voronoi approximation,
    which always partitioned space so no two coaches' areas could ever
    touch) can genuinely overlap on the map if two coaches' Territory
    Postcode Areas fields both include the same district - a data problem
    on their Coach records, not something to silently draw over. Returns
    [{"district": "TW9", "coach_labels": ["Fiona ...", "Cara ..."]}, ...]
    so office can see exactly which districts are double-claimed and by
    whom, sorted for a stable display order.
    """
    coaches_by_district = {}

    for coach_name, features in (territory_boundaries or {}).items():
        for feature in features or []:
            district = (feature.get("properties") or {}).get("name")
            if not district:
                continue
            coaches_by_district.setdefault(district, set()).add(coach_name)

    overlaps = []
    for district, coach_names in coaches_by_district.items():
        if len(coach_names) < 2:
            continue

        overlaps.append({
            "district": district,
            "coach_labels": sorted(get_coach_label(name) for name in coach_names),
        })

    overlaps.sort(key=lambda row: row["district"])
    return overlaps
