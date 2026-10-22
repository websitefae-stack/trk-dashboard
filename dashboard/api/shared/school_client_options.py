"""
Public, guest-safe lookup of current School clients - just their
display names, nothing else. Powers the live school picker on the
Student Resilience Survey and Children's Wellbeing Check-In (see
patches/add_live_school_options_script.py) - both are public, no-login
forms a child fills in themselves, and Client holds private family/
child data Guest correctly can't read directly, so this is the one
narrow, deliberately-safe exception: no other Client field, and no
Client record ID, is ever returned here - only the name, and only for
client_type "School".

This always reflects whichever Client records are tagged School right
now - there's nothing to fall out of date, unlike the Select field's
own baked-in options (set by switch_survey_school_fields_to_select.py
and kept only as a fallback in case this call fails on a given page
load - see that patch's own docstring).
"""

import frappe

CLIENT_DOCTYPE = "Client"
SCHOOL_CLIENT_TYPE = "School"


@frappe.whitelist(allow_guest=True)
def get_school_client_names():
    if not frappe.db.exists("DocType", CLIENT_DOCTYPE):
        return []

    names = frappe.get_all(
        CLIENT_DOCTYPE,
        filters={"client_type": SCHOOL_CLIENT_TYPE},
        pluck="full_name",
        ignore_permissions=True,
    )
    return sorted({(name or "").strip() for name in names if (name or "").strip()})
