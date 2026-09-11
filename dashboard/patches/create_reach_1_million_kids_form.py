"""
Creates "Help Us Reach 1 Million Kids" as a real DocType + Web Form,
same pattern as the other standalone forms (see
create_podcast_guest_booking_form.py) - a referral form for anyone to
introduce a school to The Resilient Kid, not tied to any existing
client or contact. Hub-branded, franchisor-only visibility (not shown
to coaches on the Links page).

Plain response capture, not a scored assessment - no validate hook
needed. Every field is required, matching the source form. Includes
the leading Section Break and title-wrap CSS rule from the start (see
prepend_section_break_to_standalone_forms.py /
fix_standalone_form_titles_and_css.py for why both matter).

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Reach 1 Million Kids Referral"
WEB_FORM_ROUTE = "reach-1-million-kids"

HEAR_MORE_OPTIONS = "Yes\nNo"

INTRODUCTION_TEXT = (
    "<p><em>Your mission, should you choose to accept it&hellip;</em></p>"
    "<p><strong>Connect The Resilient Kid with ONE school.</strong></p>"
    "<p>We're on a mission to reach 1 million children with practical tools that help "
    "them understand their brains, regulate their emotions and build resilience.</p>"
    "<p>Know a headteacher, SENCO, pastoral lead, teacher or school that needs to know "
    "about us?</p>"
    "<p>Make the introduction below.</p>"
)

CUSTOM_CSS = """
/* Hub logo at top */

.web-form-container::before {
    content: "";
    display: block;
    height: 140px;
    background-image: url("/files/TRHub_Logo.jpg");
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
}

/* Brand logos underneath */

.web-form-container::after {
    content: "";
    display: block;
    height: 60px;
    margin-top: -10px;
    margin-bottom: 30px;
    background-image:
        url("/files/TRKid_Wordmark_Logo.png"),
        url("/files/TRTeen_Wordmark_Logo.png"),
        url("/files/TRPeople_Wordmark_Logo.png"),
        url("/files/TRSchool_Wordmark_Logo.png");
    background-repeat: no-repeat, no-repeat, no-repeat, no-repeat;
    background-size: 120px auto, 120px auto, 120px auto, 120px auto;
    background-position:
        calc(50% - 210px) center,
        calc(50% - 70px) center,
        calc(50% + 70px) center,
        calc(50% + 210px) center;
}

/* Form styling */

.web-form-container {
    max-width: 1000px;
    margin: 0 auto;
}

.section-head {
    color: #e84862 !important;
    font-weight: 700 !important;
}

.btn-primary {
    background: #e84862 !important;
    border-color: #e84862 !important;
    border-radius: 8px !important;
    padding: 14px 32px !important;
    font-weight: 600 !important;
}

.btn-primary:hover {
    background: #9A4795 !important;
    border-color: #9A4795 !important;
}

/* Let the form title wrap onto multiple lines instead of being cut off
   with an ellipsis - the full form name should always be readable. */
.web-form-container .ellipsis,
.web-form-container h1,
.web-form-container .title {
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    word-break: break-word !important;
}
"""


def _doctype_fields():
    return [
        {"fieldname": "form_top_section", "fieldtype": "Section Break"},
        {"fieldname": "referrer_name", "fieldtype": "Data", "label": "Your Name", "reqd": 1},
        {
            "fieldname": "referrer_email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Your Email",
            "description": "So we can thank you and enter you into a prize draw.",
            "reqd": 1,
        },
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1},
        {
            "fieldname": "connection_details",
            "fieldtype": "Small Text",
            "label": "Who Should We Connect With?",
            "description": "Name/email if you know it - or simply tell us anything that might help.",
            "reqd": 1,
        },
        {
            "fieldname": "wants_to_hear_more",
            "fieldtype": "Select",
            "label": "I'd Like to Hear More From The Resilient Kid Too.",
            "options": HEAR_MORE_OPTIONS,
            "reqd": 1,
        },
    ]


def execute():
    _create_doctype()
    _create_web_form()


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": _doctype_fields(),
        "permissions": [
            {
                "role": "System Manager",
                "read": 1, "write": 1, "create": 1, "delete": 1,
                "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
            },
        ],
        "sort_field": "creation",
        "sort_order": "DESC",
        "track_changes": 1,
    })
    doc.insert(ignore_permissions=True)


def _create_web_form():
    if frappe.db.exists("Web Form", {"route": WEB_FORM_ROUTE}):
        return
    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "Help Us Reach 1 Million Kids",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": INTRODUCTION_TEXT,
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": "Thanks for the introduction - we'll take it from here.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
