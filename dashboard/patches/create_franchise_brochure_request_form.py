"""
Creates "Franchise Brochure Request" as a real DocType + Web Form, same
pattern as the other standalone forms - replaces the MailerLite popup
currently on /trh-franchise (built directly on the live site, outside
any repo), which captures name/email and hands off to MailerLite
entirely outside Frappe.

Deliberately does NOT create a Client Lead - downloading the brochure is
a much lighter-touch action than completing the Information Sheet
(which does create one, see franchise_info_sheet.py), so this stays out
of Ashley's Leads pipeline until someone actually shows real interest.

Hub-branded, franchisor-only visibility. success_message tells the
visitor to check their email rather than linking straight to the
brochure page - resilient_domains' /franchise-brochure is now token-
gated (see add_franchise_brochure_request_token.py), only reachable
via the link franchise_brochure.send_brochure_link emails out.

Runs automatically on the next `bench migrate` - no manual step needed.
Ashley still needs to update /trh-franchise's "Download Brochure" button
to link here instead of opening the MailerLite popup - that page isn't
in any repo this session has access to.
"""

import frappe

DOCTYPE_NAME = "Franchise Brochure Request"
WEB_FORM_ROUTE = "franchise-brochure-request"

CUSTOM_CSS = """
/* Hub logo at top - transparent PNG, not the flattened JPG, since the
   JPG can never have a transparent background (shows as an opaque
   white rectangle). See restyle_franchise_brochure_request_form.py if
   this needs updating on an already-live site. */

.web-form-container::before {
    content: "";
    display: block;
    height: 140px;
    margin-top: 28px;
    background-image: url("/files/TRHub_Logo.png");
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
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}

.section-head {
    color: #582581 !important;
    font-weight: 700 !important;
}

.btn-primary {
    background: #582581 !important;
    border-color: #582581 !important;
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
        # Plain text, no markup/link - Frappe's web form renderer shows
        # success_message as-is rather than as HTML (confirmed live:
        # an earlier HTML version rendered as raw visible tags, not a
        # link), and /franchise-brochure always bounces a visitor back
        # here without a real token anyway. See fix_franchise_brochure_
        # success_message.py for the matching live-site patch.
        "success_message": (
            "Thanks! Check your email - we've just sent your personal link to the brochure."
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
