"""
Creates "Franchise Brochure Request" as a real DocType + Web Form, same
pattern as the other standalone forms - replaces the MailerLite popup
currently on /trh-franchise (built directly on the live site, outside
any repo), which captures name/email and hands off to MailerLite
entirely outside Frappe.

Submitting this form is also the Email Sequence engine's trigger point
(see patches/create_email_sequence_doctypes.py) - Ashley sets up an
Email Sequence in Desk with trigger_doctype = "Franchise Brochure
Request", trigger_email_field = "email", and it enrols automatically,
no code change needed. Deliberately does NOT create a Client Lead -
downloading the brochure is a much lighter-touch action than completing
the Information Sheet (which does create one, see
franchise_info_sheet.py), so this stays out of Ashley's Leads pipeline
until someone actually shows real interest.

Hub-branded, franchisor-only visibility. success_message links straight
to the (noindex, direct-link-only) brochure page at
resilient_domains' /franchise-brochure.

Runs automatically on the next `bench migrate` - no manual step needed.
Ashley still needs to update /trh-franchise's "Download Brochure" button
to link here instead of opening the MailerLite popup - that page isn't
in any repo this session has access to.
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure Request"
WEB_FORM_ROUTE = "franchise-brochure-request"

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
        {"fieldname": "full_name", "fieldtype": "Data", "label": "Full Name", "reqd": 1},
        {"fieldname": "email", "fieldtype": "Data", "options": "Email", "label": "Email Address", "reqd": 1},
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
        "title": "Get the Franchise Brochure",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": "<p>Pop your details below and we'll send you straight to the brochure.</p>",
        "button_label": "Get the Brochure",
        "success_title": "Here you go!",
        "success_message": (
            '<p>Thanks! <a href="/franchise-brochure">Click here to view the brochure</a>.</p>'
        ),
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
