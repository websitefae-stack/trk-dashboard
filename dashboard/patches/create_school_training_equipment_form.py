"""
Creates "School Training Equipment Form" as a real DocType + Web Form,
same pattern as create_school_cpd_training_booking_form.py - a logistics
form for prepping the room/equipment for a school's training session,
separate from the booking form itself.

Branded the same way: hide_navbar/hide_footer + custom_css (School
wordmark at the top), and scoped to School/TRS Brand Access coaches
only via the Brand Access fields (add_web_form_brand_access_fields.py) -
this form only makes sense for coaches actually running School
training.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "School Training Equipment Response"
WEB_FORM_ROUTE = "school-training-equipment-form"

EQUIPMENT_FIELDS = [
    ("equipment_projector", "Projector"),
    ("equipment_smart_board", "Smart Board"),
    ("equipment_hdmi_cable", "HDMI Cable"),
    ("equipment_laptop", "Laptop"),
    ("equipment_flipchart_stand", "Flipchart & Stand"),
    ("equipment_flipchart_pens", "Flipchart Pens"),
    ("equipment_extension_leads", "Extension Leads"),
    ("equipment_whiteboard_markers", "Whiteboard & Markers"),
]

ROOM_SETUP_OPTIONS = "\n".join([
    "Classroom style", "Boardroom style", "Cabaret style", "Theatre style", "Other",
])

INTRODUCTION_TEXT = (
    "<p>Please complete this form so we can confirm and prepare for your school's "
    "training session.</p>"
    "<p>The details you provide will help us:</p>"
    "<ul>"
    "<li>Plan the session according to your chosen modules.</li>"
    "<li>Ensure the room is set up appropriately.</li>"
    "<li>Confirm the equipment needed.</li>"
    "<li>Coordinate with your contact person on the day.</li>"
    "</ul>"
    "<p>Accurate information will allow us to deliver a smooth and effective "
    "training experience for your staff.</p>"
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
"""


def _doctype_fields():
    fields = [
        {"fieldname": "form_top_section", "fieldtype": "Section Break"},
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name"},
        {
            "fieldname": "training_date",
            "fieldtype": "Date",
            "label": "Date of Planned Training",
            "reqd": 1,
        },
        {"fieldname": "number_of_staff", "fieldtype": "Int", "label": "Number of Staff Attending", "reqd": 1},
        {
            "fieldname": "attendee_names",
            "fieldtype": "Small Text",
            "label": "List of Names of Attendees (if possible)",
        },
        {"fieldname": "room_setup_section", "fieldtype": "Section Break", "label": "Training Room Setup"},
        {
            "fieldname": "training_room_setup",
            "fieldtype": "Select",
            "label": "Training Room Setup",
            "options": ROOM_SETUP_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "room_setup_other",
            "fieldtype": "Data",
            "label": "If Other, Please Specify",
            "depends_on": "eval:doc.training_room_setup=='Other'",
        },
        {"fieldname": "max_room_capacity", "fieldtype": "Int", "label": "Maximum Room Capacity", "reqd": 1},
        {"fieldname": "equipment_section", "fieldtype": "Section Break", "label": "Equipment Available"},
    ]

    for fieldname, label in EQUIPMENT_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields.append({
        "fieldname": "equipment_other",
        "fieldtype": "Data",
        "label": "Other Equipment (please specify)",
    })

    fields += [
        {"fieldname": "timing_section", "fieldtype": "Section Break", "label": "Timing"},
        {"fieldname": "training_start_time", "fieldtype": "Time", "label": "Training Start Time", "reqd": 1},
        {"fieldname": "training_finish_time", "fieldtype": "Time", "label": "Training Finish Time", "reqd": 1},
        {"fieldname": "breaks_planned", "fieldtype": "Data", "label": "Breaks Planned"},
        {"fieldname": "lunch_time", "fieldtype": "Data", "label": "Lunch Time (if applicable)"},
        {"fieldname": "contact_section", "fieldtype": "Section Break", "label": "On The Day Contact"},
        {
            "fieldname": "on_day_contact_name",
            "fieldtype": "Data",
            "label": "Name of Person Who Will Meet Trainer on the Day",
            "reqd": 1,
        },
        {
            "fieldname": "on_day_contact_mobile",
            "fieldtype": "Data",
            "label": "Mobile Number of the Person Who Will Meet the Trainer on the Day",
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
        "title": "School Training Equipment Form",
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
        "success_message": "Your training equipment details have been received - we'll be in touch to confirm.",
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
