"""
Two fixes for the 8 standalone forms created this batch, applied
directly to the Web Form records already created on this site (editing
the original creation patches alone doesn't reach them - each is
guarded by "does this already exist" and won't re-run):

1. The form title was being cut off with an ellipsis instead of
   wrapping onto a second line (confirmed live: "The Resilient Schools
   CPD Training Boo..."). Every form's custom_css gains a rule making
   the title wrap instead.

2. Three titles repeated the "The Resilient Schools"/"Resilient Kid"
   branding that's already shown via the logo at the top of the page -
   shortened to just the distinctive part of the name, both to read
   better and to need less room before wrapping.
"""

import frappe

SCHOOL_LOGO = "/files/TRSchool_Wordmark_Logo.png"
HUB_LOGO = "/files/TRHub_Logo.jpg"


def _custom_css(logo_url):
    return f"""
/* Hub logo at top */

.web-form-container::before {{
    content: "";
    display: block;
    height: 140px;
    background-image: url("{logo_url}");
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
}}

/* Brand logos underneath */

.web-form-container::after {{
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
}}

/* Form styling */

.web-form-container {{
    max-width: 1000px;
    margin: 0 auto;
}}

.section-head {{
    color: #e84862 !important;
    font-weight: 700 !important;
}}

.btn-primary {{
    background: #e84862 !important;
    border-color: #e84862 !important;
    border-radius: 8px !important;
    padding: 14px 32px !important;
    font-weight: 600 !important;
}}

.btn-primary:hover {{
    background: #9A4795 !important;
    border-color: #9A4795 !important;
}}

/* Let the form title wrap onto multiple lines instead of being cut off
   with an ellipsis - the full form name should always be readable. */
.web-form-container .ellipsis,
.web-form-container h1,
.web-form-container .title {{
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    word-break: break-word !important;
}}
"""


# route -> (logo_url, new title or None to leave the title as-is)
FORM_UPDATES = {
    "school-cpd-training-booking": (SCHOOL_LOGO, "CPD Training Booking Form"),
    "school-training-equipment-form": (SCHOOL_LOGO, None),
    "parent-media-consent-form": (SCHOOL_LOGO, None),
    "school-staff-pre-training-questionnaire": (SCHOOL_LOGO, "Pre-Training Questionnaire for School Staff"),
    "school-cpd-staff-feedback-form": (SCHOOL_LOGO, "CPD Training - Staff Feedback Form"),
    "staff-media-release-form": (SCHOOL_LOGO, None),
    "podcast-guest-information": (HUB_LOGO, None),
    "franchise-termination-questionnaire": (HUB_LOGO, None),
}


def execute():
    for route, (logo_url, new_title) in FORM_UPDATES.items():
        web_form_name = frappe.db.get_value("Web Form", {"route": route}, "name")
        if not web_form_name:
            continue

        updates = {"custom_css": _custom_css(logo_url)}
        if new_title:
            updates["title"] = new_title

        frappe.db.set_value("Web Form", web_form_name, updates)

    frappe.db.commit()
