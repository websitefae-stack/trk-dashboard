"""
Creates "Podcast Guest Booking Form" as a real DocType + Web Form, same
pattern as the other standalone forms (see
create_school_cpd_training_booking_form.py), but Hub-branded rather
than School-branded (TRHub_Logo.jpg at the top, not a school wordmark)
and franchisor-only - this is sent to prospective podcast guests by
Ashley personally, not something coaches need to see or share, so
custom_show_in_coach_reports stays off and no Brand Access is set.

Two file-upload fields (PDF sheet, headshot) use the "Attach" fieldtype -
both optional, matching the source form (neither was marked required).

Plain response capture, not a scored assessment - no validate hook
needed.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Podcast Guest Booking"
WEB_FORM_ROUTE = "podcast-guest-information"

PDF_SHEET_OPTIONS = "Yes\nNo\nMaybe"

INTRODUCTION_TEXT = (
    "<p><strong>Contact information - Please read the following:</strong></p>"
    "<p>Round table - the format for this podcast is an open, honest and frank chat. It "
    "is informal, however, we want the audience to have the feeling of coming away with "
    "info, shared experience or a signpost to help. You might be coming to this with a "
    "lived experience, so only share what you feel happy with. You may be coming as an "
    "expert in your field, please don't promote your work - Ashley will give you an "
    "opportunity at the end of the podcast.</p>"
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
        {"fieldname": "email", "fieldtype": "Data", "options": "Email", "label": "Email", "reqd": 1},
        {"fieldname": "guest_name", "fieldtype": "Data", "label": "Name"},
        {"fieldname": "phone_number", "fieldtype": "Data", "label": "Phone Number"},
        {
            "fieldname": "unavailable_days_times",
            "fieldtype": "Small Text",
            "label": "Any Particular Days and Times You Are NOT Available?",
            "description": "They are mostly recorded on Thurs/Fridays.",
        },
        {"fieldname": "location", "fieldtype": "Data", "label": "Where Are You Located?", "reqd": 1},
        {"fieldname": "website_address", "fieldtype": "Data", "label": "Website Address"},
        {
            "fieldname": "social_media_links",
            "fieldtype": "Small Text",
            "label": "Links to Social Media (Facebook, Instagram, LinkedIn, etc) - List Them Below",
            "reqd": 1,
        },
        {
            "fieldname": "interview_topic",
            "fieldtype": "Small Text",
            "label": "Interview Topic - What Are You Bringing to the Table?",
            "reqd": 1,
        },
        {
            "fieldname": "areas_of_expertise",
            "fieldtype": "Small Text",
            "label": "What Topics Do You Feel You Have Experience/Expertise On?",
        },
        {
            "fieldname": "top_tips",
            "fieldtype": "Small Text",
            "label": "Any Top Tips That You Would Want to Share? (optional)",
        },
        {
            "fieldname": "signpost",
            "fieldtype": "Small Text",
            "label": "What Would You Like to Signpost If Any (book, course, socials etc.)",
        },
        {
            "fieldname": "has_pdf_sheet",
            "fieldtype": "Select",
            "label": "Have You Got a PDF Sheet? (optional)",
            "options": PDF_SHEET_OPTIONS,
        },
        {
            "fieldname": "pdf_sheet_upload",
            "fieldtype": "Attach",
            "label": "If Yes, Please Upload It Here",
        },
        {
            "fieldname": "headshot_upload",
            "fieldtype": "Attach",
            "label": "Please Upload Your Headshot",
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
        "title": "Podcast Guest Booking Form",
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
        "success_message": "Thanks - we'll be in touch about your podcast slot.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
