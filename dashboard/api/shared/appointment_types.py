"""
Central lookup for appointment-type booking configuration, stored as
Custom Fields directly on the site's own "Appointment Template" doctype
(see patches/add_appointment_template_booking_fields.py). This means Ashley
can add a brand new appointment type, or change how an existing one
behaves (public booking on/off, slot length, whether it converts a Lead to
a Client) entirely from the Frappe desk - Appointment Template list - with
no code change required.

Coach.appointment_types.appointment_name links straight to an Appointment
Template docname, but a Lead's own appointment_type is a freeform label
picked/typed at creation time, so lookups here match by docname OR by
whichever label field the site's Appointment Template happens to use
(appointment_type / title / template_name), case-insensitive "contains" -
the same relaxed match already used across the leads/booking system.
"""

import frappe

DEFAULT_DURATION_MINUTES = 60

# Fallback only - used if this site hasn't run `bench migrate` since the
# custom fields were added yet, so public booking doesn't silently break
# in the gap between a code deploy and the next migrate.
LEGACY_EXCLUDED_LABEL_FRAGMENTS = ["supervision", "parent check"]
LEGACY_NON_CLIENT_LABEL_FRAGMENTS = ["franchisee call"]

CUSTOM_FIELDS = [
    "custom_public_booking_enabled",
    "custom_booking_duration_minutes",
    "custom_creates_client_on_conversion",
]


def _has_booking_config_fields():
    if not frappe.db.exists("DocType", "Appointment Template"):
        return False

    return frappe.get_meta("Appointment Template").has_field("custom_public_booking_enabled")


def get_matching_templates(label):
    if not label or not frappe.db.exists("DocType", "Appointment Template"):
        return []

    label_lower = label.lower()
    meta = frappe.get_meta("Appointment Template")

    candidate_fields = ["name"]
    for fieldname in ["appointment_type", "title", "template_name"]:
        if meta.has_field(fieldname):
            candidate_fields.append(fieldname)

    fetch_fields = list(candidate_fields)
    for fieldname in CUSTOM_FIELDS:
        if meta.has_field(fieldname):
            fetch_fields.append(fieldname)

    rows = frappe.get_all("Appointment Template", fields=fetch_fields, limit_page_length=1000)

    matches = []
    for row in rows:
        for fieldname in candidate_fields:
            value = row.get(fieldname) or ""
            if label_lower in value.lower():
                matches.append(row)
                break

    return matches


def is_publicly_bookable(label):
    if not label:
        return False

    label_lower = label.lower()

    # Parent Check-In and Supervision must never be publicly bookable, full
    # stop - not just as the pre-migration fallback default. Whatever
    # custom_public_booking_enabled happens to be set to on their
    # Appointment Template (e.g. left ticked from before this per-type
    # config existed, or toggled by mistake) must never be able to put a
    # staff-only appointment type on a coach's public profile page.
    if any(fragment in label_lower for fragment in LEGACY_EXCLUDED_LABEL_FRAGMENTS):
        return False

    if not _has_booking_config_fields():
        return True

    matches = get_matching_templates(label)
    return any(int(row.get("custom_public_booking_enabled") or 0) for row in matches)


def get_duration_minutes(label):
    for row in get_matching_templates(label):
        minutes = row.get("custom_booking_duration_minutes")
        if minutes:
            try:
                return int(minutes)
            except Exception:
                pass

    return DEFAULT_DURATION_MINUTES


def creates_client_on_conversion(label):
    if not label:
        return True

    if not _has_booking_config_fields():
        label_lower = label.lower()
        return not any(fragment in label_lower for fragment in LEGACY_NON_CLIENT_LABEL_FRAGMENTS)

    matches = get_matching_templates(label)
    if not matches:
        return True

    return any(int(row.get("custom_creates_client_on_conversion") if row.get("custom_creates_client_on_conversion") is not None else 1) for row in matches)


def _coach_public_booking_base(coach_name):
    """
    Shared by get_coach_public_booking_link and get_coach_public_
    booking_cards: this coach's /trh-coaches slug (None if they have no
    public profile at all) and the list of appointment types they offer
    that is_publicly_bookable() actually allows - never Parent Check-In,
    Supervision, etc, regardless of what the coach has ticked active,
    since a link shared with the public can't surface a staff-only
    session type. Always the Hub-branded /trh-coaches profile (same
    precedent as /book-franchise-call's own fallback) regardless of
    which brand(s) the coach actually works under.

    Returns (base_url, public_types) or (None, []) if this coach has no
    public profile to link to at all.
    """
    if not coach_name or not frappe.db.exists("Coach", coach_name):
        return None, []

    coach = frappe.get_doc("Coach", coach_name)

    if not coach.get("profile_page_enabled"):
        return None, []

    access_rows = frappe.get_all(
        "Coach Brand Access",
        filters={"parent": coach_name, "parenttype": "Coach", "display_on_website": 1},
        fields=["public_profile_slug"],
        order_by="idx asc",
        limit_page_length=1,
    )

    if not access_rows:
        return None, []

    slug = access_rows[0].public_profile_slug

    if not slug:
        display_name = coach.get("coach_name") or coach_name
        slug = frappe.scrub(display_name).replace("_", "-")

    public_types = []
    seen = set()

    for row in coach.get("appointment_types") or []:
        if not row.get("active"):
            continue
        name = row.get("appointment_name")
        if not name or name in seen:
            continue
        if not is_publicly_bookable(name):
            continue
        seen.add(name)
        public_types.append(name)

    return f"/trh-coaches/{slug}", public_types


def get_coach_public_booking_link(coach_name, source="Coach Share"):
    """
    A coach's own shareable "book with me" link, for their Your Logins
    tab's QR code (see profile.get_coach_login_links) - same deep-link
    pattern resilient_domains' /book-franchise-call already uses
    (?book=<type>&source=<source>#appointments, picked up by
    coach-booking.js's openFromQueryString), just resolved for THIS
    specific coach instead of "whoever currently offers X".

    One combined link: deep-links straight into the one public type if
    they only offer one (the common case - an intro/consultation call);
    with several, links to their profile's own appointments section
    instead and lets the visitor pick, since there's no single right one
    to guess. See get_coach_public_booking_cards for a card PER type
    instead (what the Links page actually uses).
    """
    base_url, public_types = _coach_public_booking_base(coach_name)

    if not base_url:
        return None

    if len(public_types) == 1:
        return f"{base_url}?book={frappe.utils.quote(public_types[0])}&source={frappe.utils.quote(source)}#appointments"

    return f"{base_url}#appointments"


def get_coach_public_booking_cards(coach_name, source="Coach Links Page"):
    """
    One entry per publicly bookable appointment type this coach offers -
    each its own deep link straight into that type's booking modal (same
    ?book=<type>&source=<source>#appointments pattern as /book-franchise-
    call), for the Links page's "card per booking option" (see
    form_reports.get_form_links). Never includes anything is_publicly_
    bookable() excludes (Parent Check-In, Supervision, etc). Returns []
    if this coach has no public profile or no publicly bookable type.
    """
    base_url, public_types = _coach_public_booking_base(coach_name)

    if not base_url:
        return []

    return [
        {
            "appointment_name": appointment_name,
            "url": f"{base_url}?book={frappe.utils.quote(appointment_name)}&source={frappe.utils.quote(source)}#appointments",
        }
        for appointment_name in public_types
    ]


def get_coach_offering(label):
    """
    First Coach with an active appointment_types row matching label (same
    relaxed "contains" match as the rest of this module) - lets a link
    elsewhere on the site (e.g. the /book-franchise-call redirect,
    resilient_domains) find whichever coach currently handles a given
    appointment type without hardcoding a name, so it keeps working if
    that changes. Returns None if nobody currently offers it.
    """
    if not label or not frappe.db.exists("DocType", "Coach"):
        return None

    label_lower = label.lower()

    if not frappe.get_meta("Coach").has_field("appointment_types"):
        return None

    for coach_name in frappe.get_all("Coach", pluck="name"):
        coach_doc = frappe.get_doc("Coach", coach_name)
        for row in coach_doc.get("appointment_types") or []:
            if not row.get("active"):
                continue
            if label_lower in (row.get("appointment_name") or "").lower():
                return coach_name

    return None
