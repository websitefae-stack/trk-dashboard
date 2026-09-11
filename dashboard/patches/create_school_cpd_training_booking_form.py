"""
Creates "The Resilient Schools CPD Training Booking Form" as a real
DocType + Web Form, the same way every other public form on this site
already works (see form_reports.py's own module docstring) - a custom
(Desk-style) DocType discovered automatically once its Module is
"Forms", with a public Web Form on top.

A straightforward booking intake, not a scored assessment like the
wellbeing/care-language forms - no validate hook needed, just captures
what the school submits.

Branded page: hide_navbar/hide_footer + custom_css (School wordmark logo
at the top instead of the generic Hub logo, brand logos underneath,
themed section headings/submit button) per how Ashley wants every one of
these standalone forms to look.

Runs automatically on the next `bench migrate` (part of a normal
deploy) - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "School CPD Training Booking"
WEB_FORM_ROUTE = "school-cpd-training-booking"

MODULE_FIELDS = [
    ("module_brain_smart_behaviour", "Brain Smart & Behaviour"),
    ("module_language_we_use", "The Language We Use"),
    ("module_components_of_resilience", "Components of Resilience"),
    ("module_environment_we_create", "The Environment We Create"),
    ("module_meeting_them_where_they_are", "Meeting Them Where They Are At"),
    ("module_restore_repair", "Restore & Repair"),
]

INTRODUCTION_TEXT = (
    "<p>Please complete this form to book CPD training for your school.</p>"
    "<p>The information you provide will help us:</p>"
    "<ul>"
    "<li>Confirm your chosen modules.</li>"
    "<li>Plan the date and time of training.</li>"
    "<li>Record the number of staff attending.</li>"
    "<li>Ensure we have the right contact details for booking and payment.</li>"
    "</ul>"
    "<p>Each module runs for approximately one hour. You may choose 2, 3, or 5 "
    "modules per booking.</p>"
    "<p>Accurate details will allow us to confirm your booking quickly and "
    "deliver the training smoothly.</p>"
)

CUSTOM_CSS = """
/* Hub logo at top */

.web-form-container::before {
    content: "";
    display: block;
    height: 140px;
    background-image: url("/files/TRSchool_Wordmark_Logo.png");
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
    fields = [
        {"fieldname": "form_top_section", "fieldtype": "Section Break"},
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1},
        {"fieldname": "school_address", "fieldtype": "Small Text", "label": "School Address", "reqd": 1},
        {"fieldname": "school_phone", "fieldtype": "Data", "label": "School Phone Number", "reqd": 1},
        {
            "fieldname": "modules_section",
            "fieldtype": "Section Break",
            "label": "Modules (please choose 2, 3 or 5)",
        },
    ]

    for fieldname, label in MODULE_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {"fieldname": "booking_details_section", "fieldtype": "Section Break", "label": "Booking Details"},
        {"fieldname": "number_of_staff", "fieldtype": "Int", "label": "Number of Staff Attending", "reqd": 1},
        {
            "fieldname": "preferred_dates",
            "fieldtype": "Data",
            "label": "Preferred Date(s) for Training",
            "reqd": 1,
        },
        {"fieldname": "approximate_times", "fieldtype": "Data", "label": "Approximate Time(s)", "reqd": 1},
        {"fieldname": "contacts_section", "fieldtype": "Section Break", "label": "Contact Details"},
        {
            "fieldname": "booking_contact_name",
            "fieldtype": "Data",
            "label": "Name of Person Responsible for Booking",
            "reqd": 1,
        },
        {
            "fieldname": "booking_contact_email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Email of Person Responsible for Booking",
            "reqd": 1,
        },
        {
            "fieldname": "invoice_contact_name",
            "fieldtype": "Data",
            "label": "Name of Person Responsible for Payment of the Invoice",
            "reqd": 1,
        },
        {
            "fieldname": "invoice_contact_email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Email Address for the Person Responsible for the Invoice",
            "reqd": 1,
        },
        {
            "fieldname": "additional_information",
            "fieldtype": "Small Text",
            "label": "Additional Information You Would Like to Share",
        },
    ]

    return fields


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
        "title": "CPD Training Booking Form",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": INTRODUCTION_TEXT,
        "button_label": "Submit Booking",
        "success_title": "Thank you!",
        "success_message": "Your CPD training booking request has been received - we'll be in touch to confirm.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 1,
        "custom_brand_access_school": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
