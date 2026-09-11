"""
Creates "Franchise Termination Questionnaire" as a real DocType + Web
Form, same pattern as the other standalone forms (see
create_podcast_guest_booking_form.py) - Hub-branded, franchisor-only
visibility (not shown to coaches on the Links page), sent to a
franchisee who's leaving, to help with offboarding.

Plain response capture, not a scored assessment - no validate hook
needed. Every field is required, matching the source form.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Franchise Termination Response"
WEB_FORM_ROUTE = "franchise-termination-questionnaire"

INTRODUCTION_TEXT = (
    "<p>Please complete the following questions to help us with your offboarding.</p>"
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
        {"fieldname": "full_name", "fieldtype": "Data", "label": "Your Full Name and Surname", "reqd": 1},
        {
            "fieldname": "personal_email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Your Personal Email Address",
            "reqd": 1,
        },
        {
            "fieldname": "client_status",
            "fieldtype": "Small Text",
            "label": "Where Are You Up to With Each Client?",
            "reqd": 1,
        },
        {
            "fieldname": "client_departure_messaging",
            "fieldtype": "Small Text",
            "label": "What Are You Telling Clients About Your Departure?",
            "reqd": 1,
        },
        {
            "fieldname": "public_social_messaging",
            "fieldtype": "Small Text",
            "label": "What Should We Say Publicly or on Social Media?",
            "reqd": 1,
        },
        {
            "fieldname": "upcoming_sessions_events",
            "fieldtype": "Small Text",
            "label": "Do You Have Any Upcoming Sessions/Events Booked?",
            "reqd": 1,
        },
        {
            "fieldname": "logins_and_accounts",
            "fieldtype": "Small Text",
            "label": "Please List Any Login Details or Accounts We Might Need Access To",
            "description": "e.g. Canva, Meta Business Suite.",
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
        "title": "Franchise Termination Questionnaire",
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
        "success_message": "Your answers have been received - thank you.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
