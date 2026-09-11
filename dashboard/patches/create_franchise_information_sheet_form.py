"""
Creates "Information Sheet - TRK Franchise" as a real DocType + Web
Form, same pattern as the other standalone forms (see
create_podcast_guest_booking_form.py) - a prospective franchisee fills
this in after downloading the brochure, before Ashley reaches out to
book a call. Hub-branded, franchisor-only visibility.

Two questions ("Experience with Children", "How did you hear about the
opportunity?") looked identical in the source form's plain-text export
(a list of options ending in "Other:") - no way to tell from that
whether either was meant to allow multiple answers. Built as: Experience
with Children -> checkboxes (multiple experience types are plausible
for one person), How did you hear -> single Select with an Other
option (a primary source is the more common shape for that question).
Worth checking with Ashley against the real Google Form if this guess
is wrong for either.

Plain response capture, not a scored assessment - no validate hook
needed.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Franchise Information Sheet Response"
WEB_FORM_ROUTE = "franchise-information-sheet"

EXPERIENCE_FIELDS = [
    ("experience_primary_school", "Primary School"),
    ("experience_own_children", "Own Children"),
    ("experience_youth_club", "Youth Club"),
    ("experience_child_therapist", "Child Therapist"),
]

HEARD_ABOUT_OPTIONS = "\n".join([
    "Facebook", "Instagram", "Friend Recommend", "Previous Client", "Other",
])

READY_TO_INVEST_OPTIONS = "Yes\nNo\nUndecided"
TIMELINE_OPTIONS = "3 months\n6 months\n12 months"
FOLLOW_UP_METHOD_OPTIONS = "Email\nPhone\nFace to Face"
YES_NO_OPTIONS = "Yes\nNo"

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
    fields = [
        {"fieldname": "form_top_section", "fieldtype": "Section Break"},
        {"fieldname": "full_name", "fieldtype": "Data", "label": "First and Last Name", "reqd": 1},
        {"fieldname": "email", "fieldtype": "Data", "options": "Email", "label": "Email Address", "reqd": 1},
        {"fieldname": "phone_number", "fieldtype": "Data", "label": "Telephone Number"},
        {"fieldname": "location", "fieldtype": "Data", "label": "Location (City/Town)", "reqd": 1},
        {
            "fieldname": "current_occupation",
            "fieldtype": "Data",
            "label": "Current Occupation/Business",
            "reqd": 1,
        },
        {
            "fieldname": "experience_section",
            "fieldtype": "Section Break",
            "label": "Experience with Children",
        },
    ]

    for fieldname, label in EXPERIENCE_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields.append({
        "fieldname": "experience_other",
        "fieldtype": "Data",
        "label": "Other (please specify)",
    })

    fields += [
        {
            "fieldname": "interest_reason",
            "fieldtype": "Small Text",
            "label": "Why Are You Interested in The Resilient Kid Franchise?",
            "reqd": 1,
        },
        {
            "fieldname": "heard_about_opportunity",
            "fieldtype": "Select",
            "label": "How Did You Hear About the Opportunity?",
            "options": HEARD_ABOUT_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "heard_about_other",
            "fieldtype": "Data",
            "label": "If Other, Please Specify",
            "depends_on": "eval:doc.heard_about_opportunity=='Other'",
        },
        {
            "fieldname": "ready_to_invest",
            "fieldtype": "Select",
            "label": "Are You Ready to Invest in a Franchise?",
            "options": READY_TO_INVEST_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "investment_timeline",
            "fieldtype": "Select",
            "label": "Preferred Investment Timeline Within",
            "options": TIMELINE_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "preferred_area_region",
            "fieldtype": "Data",
            "label": "Which Area/Region Would You Be Interested in Operating the Franchise?",
            "reqd": 1,
        },
        {
            "fieldname": "questions_and_concerns",
            "fieldtype": "Small Text",
            "label": "What Are Your Main Questions or Concerns About the Franchise?",
            "reqd": 1,
        },
        {
            "fieldname": "preferred_follow_up_method",
            "fieldtype": "Select",
            "label": "Preferred Follow-Up Method",
            "options": FOLLOW_UP_METHOD_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "wants_1to1_meeting",
            "fieldtype": "Select",
            "label": "Interested in a 1:1 Follow-Up Meeting?",
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },
        {"fieldname": "date_of_birth", "fieldtype": "Date", "label": "Please Provide Your Date of Birth"},
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
        "title": "Information Sheet - TRK Franchise",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": "Thanks for sharing this - Ashley will be in touch soon.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 0,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
