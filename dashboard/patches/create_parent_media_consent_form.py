"""
Creates "Parent/Carer Media Consent Form" as a real DocType + Web Form,
same pattern as the other School-branded forms (see
create_school_cpd_training_booking_form.py) - a consent form for the
Podcast Day event run as part of Resilient School Accreditation.

Plain consent capture, not a scored assessment - no validate hook
needed. Branded and scoped the same way as the other School forms:
navbar/footer hidden, custom CSS with the School wordmark at the top,
and School/TRS Brand Access only.

Note: the source form's Yes/No consent options were "Yes, I consent" /
"N, I do not consent" - the second option is normalised to "No, I do
not consent" here (an obvious typo in the original, not a deliberate
wording choice).

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Parent Media Consent Response"
WEB_FORM_ROUTE = "parent-media-consent-form"

YEAR_GROUP_OPTIONS = "\n".join([
    "Reception", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5", "Year 6",
    "Year 7", "Year 8", "Year 9", "Year 10", "Year 11", "Year 12", "Year 13", "Other",
])

CONSENT_OPTIONS = "Yes, I consent\nNo, I do not consent"

CONSENT_FIELDS = [
    (
        "consent_photographs_school_use",
        "Photographs - School Use",
        "Still images used internally by the school (newsletters, displays, school website).",
    ),
    (
        "consent_video_school_use",
        "Video Footage - School Use",
        "Video clips used internally by the school (website, presentations, parent events).",
    ),
    (
        "consent_social_media_trk",
        "Social Media - The Resilient Kid",
        "Photographs and/or video shared on The Resilient Kid's social media channels "
        "(Instagram, Facebook, LinkedIn, YouTube, Podcast Platforms, Website) to showcase "
        "the programme.",
    ),
    (
        "consent_podcast_audio_video",
        "Podcast Audio/Video",
        "Audio recordings from the Podcast Day, which may be published as podcast content "
        "or shared online.",
    ),
    (
        "consent_named_identification",
        "Named Identification",
        "My child may be identified by first name only in any published content.",
    ),
]

INTRODUCTION_TEXT = (
    "<p>We are hosting a Podcast Day as part of our Resilient School Accreditation with "
    "the team at The Resilient Kid. During this event, we may capture photographs, video "
    "footage, and audio recordings of pupils and staff. Please read and complete this form "
    "to let us know your wishes.</p>"
)

DECLARATION_TEXT = (
    "I confirm I have parental responsibility for the child named above and I am providing "
    "the consent choices above freely. I understand I can withdraw consent at any time by "
    "contacting the school."
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
        {"fieldname": "child_name", "fieldtype": "Data", "label": "Child's First and Last Name", "reqd": 1},
        {
            "fieldname": "year_group",
            "fieldtype": "Select",
            "label": "Year Group",
            "options": YEAR_GROUP_OPTIONS,
            "reqd": 1,
        },
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1},
        {"fieldname": "teacher_name", "fieldtype": "Data", "label": "Teacher Name", "reqd": 1},
        {"fieldname": "parent_details_section", "fieldtype": "Section Break", "label": "Parent/Carer Details"},
        {
            "fieldname": "parent_name",
            "fieldtype": "Data",
            "label": "First and Last Name",
            "reqd": 1,
        },
        {
            "fieldname": "relationship_to_child",
            "fieldtype": "Data",
            "label": "Relationship to Child",
            "description": "e.g. parent, guardian, grandparent",
            "reqd": 1,
        },
        {
            "fieldname": "parent_email",
            "fieldtype": "Data",
            "options": "Email",
            "label": "Email Address",
            "reqd": 1,
        },
        {
            "fieldname": "consent_section",
            "fieldtype": "Section Break",
            "label": "Consent Choices",
            "description": "Please indicate your consent for each type of use below.",
        },
    ]

    for fieldname, label, description in CONSENT_FIELDS:
        fields.append({
            "fieldname": fieldname,
            "fieldtype": "Select",
            "label": label,
            "options": CONSENT_OPTIONS,
            "description": description,
            "reqd": 1,
        })

    fields += [
        {
            "fieldname": "declaration_section",
            "fieldtype": "Section Break",
            "label": "Declaration and Signature",
            "description": DECLARATION_TEXT,
        },
        {
            "fieldname": "signature",
            "fieldtype": "Data",
            "label": "Signature",
            "description": "Please type your full name",
            "reqd": 1,
        },
        {"fieldname": "signed_date", "fieldtype": "Date", "label": "Date", "reqd": 1},
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
        "title": "Parent/Carer Media Consent Form",
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
        "success_message": "Your consent choices have been received - thank you.",
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
