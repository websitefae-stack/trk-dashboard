"""
Creates "Staff Media Release Form" as a real DocType + Web Form, same
pattern as create_parent_media_consent_form.py - the staff-side
equivalent of that Podcast Day consent form, for staff members
themselves rather than parents/carers on behalf of their child.

Plain consent capture, not a scored assessment - no validate hook
needed. Branded and scoped the same way as the other School forms:
navbar/footer hidden, custom CSS with the School wordmark, School/TRS
Brand Access only.

Note: as with the Parent/Carer form, the source's "N, I do not
consent" option is normalised to "No, I do not consent" here (an
obvious typo, not a deliberate wording choice).

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Staff Media Release Response"
WEB_FORM_ROUTE = "staff-media-release-form"

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
        "Video clips used internally by the school (website, presentations, CPD materials).",
    ),
    (
        "consent_social_media_trk",
        "Social Media - The Resilient Kid",
        "Photographs and/or video shared on The Resilient Kid's social media channels "
        "(Instagram, Facebook, LinkedIn, YouTube, Podcast Platforms, Website) to showcase "
        "the programme and accreditation work.",
    ),
    (
        "consent_podcast_audio_video",
        "Podcast Audio/Video",
        "Audio and/or video recordings from the Podcast Day, which may be published as "
        "podcast content, promotional material, or shared online.",
    ),
    (
        "consent_named_identification",
        "Named Identification",
        "My name and/or job title may be included alongside any published content I "
        "appear in.",
    ),
    (
        "consent_testimonial_quote_use",
        "Testimonial/Quote Use",
        "Any comments or quotes I make on camera or on the podcast may be used in "
        "marketing or promotional materials for The Resilient Kid / The Resilient School.",
    ),
]

INTRODUCTION_TEXT = (
    "<p>As a staff member taking part in our Resilient Kid Podcast Day, we would like "
    "your permission to use photographs, video, and audio recordings for the purposes "
    "described below. Participation is entirely voluntary and will not affect your role "
    "or responsibilities. It is part of our Resilient School Accreditation so any help "
    "would be greatly appreciated.</p>"
)

DECLARATION_TEXT = (
    "I confirm the details above are accurate and I am providing this consent freely. I "
    "understand I can withdraw consent at any time by contacting The Resilient Kid in "
    "writing, and that any content already published cannot be retroactively removed from "
    "third-party platforms."
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
        {"fieldname": "staff_name", "fieldtype": "Data", "label": "First and Last Name"},
        {
            "fieldname": "role_job_title",
            "fieldtype": "Data",
            "label": "Role/Job Title",
            "description": "e.g. Year 4 teacher, SENCO",
            "reqd": 1,
        },
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1},
        {"fieldname": "work_email", "fieldtype": "Data", "options": "Email", "label": "Work Email", "reqd": 1},
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
        "title": "Staff Media Release Form",
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
