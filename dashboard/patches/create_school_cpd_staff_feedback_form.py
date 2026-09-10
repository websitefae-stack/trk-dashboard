"""
Creates "The Resilient Schools CPD Training - Staff Feedback Form" as a
real DocType + Web Form, same pattern as the other School-branded forms
(see create_school_cpd_training_booking_form.py). Post-training
feedback, not a booking/consent form - no field is required, matching
the source form (no field there was marked with an asterisk either).

The "Overall, how would you rate this training?" question was a 1-10
scale in the source form - reduced to 1-5 here, same as the earlier
Pre-Training Questionnaire's rating questions, per Ashley's request to
keep every rating scale to 5 options rather than mixing 5 and 10.

Plain response capture, not a scored assessment - no validate hook
needed. Branded and scoped the same way as the other School forms:
navbar/footer hidden, custom CSS with the School wordmark, School/TRS
Brand Access only.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "School CPD Staff Feedback Response"
WEB_FORM_ROUTE = "school-cpd-staff-feedback-form"

MODULE_FIELDS = [
    ("module_components_of_resilience", "Components of Resilience"),
    ("module_brain_smart_behaviour", "Brain Smart and Behaviour"),
    ("module_meeting_them_where_they_are", "Meeting Them Where They Are At"),
    ("module_environment_we_create", "The Environment We Create"),
    ("module_language_we_use", "The Language We Use"),
]

RATING_OPTIONS = "1\n2\n3\n4\n5"
RELEVANCE_OPTIONS = "\n".join([
    "Not at all relevant", "Somewhat relevant", "Relevant", "Very relevant", "Extremely relevant",
])
CONFIDENCE_AFTER_OPTIONS = "Yes definitely\nSomewhat\nNot really"
PACE_OPTIONS = "Too short\nAbout right\nToo long"
RECOMMEND_OPTIONS = "Yes\nNo\nMaybe"
ANONYMITY_OPTIONS = (
    "Yes, I consent to my feedback being shared publicly.\n"
    "No, I do not consent to my feedback being shared publicly."
)

INTRODUCTION_TEXT = (
    "<p>Thank you for taking part in our Resilient School CPD training. Your feedback "
    "helps us improve and make sure the training has the most impact for you, your "
    "pupils, and your school.</p>"
    "<p>Please take a few minutes to complete this form.</p>"
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
        {"fieldname": "full_name", "fieldtype": "Data", "label": "Your Full Name"},
        {"fieldname": "email_address", "fieldtype": "Data", "options": "Email", "label": "Your Email Address"},
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name"},
        {"fieldname": "your_role", "fieldtype": "Data", "label": "Your Role"},
        {"fieldname": "modules_section", "fieldtype": "Section Break", "label": "Which Module(s) Did You Complete?"},
    ]

    for fieldname, label in MODULE_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {"fieldname": "feedback_section", "fieldtype": "Section Break", "label": "Feedback"},
        {
            "fieldname": "overall_rating",
            "fieldtype": "Select",
            "label": "Overall, How Would You Rate This Training?",
            "options": RATING_OPTIONS,
        },
        {
            "fieldname": "delivery_clarity",
            "fieldtype": "Select",
            "label": "How Clear and Engaging Did You Find the Delivery?",
            "options": RATING_OPTIONS,
        },
        {
            "fieldname": "content_relevance",
            "fieldtype": "Select",
            "label": "How Relevant Was the Content to Your Role?",
            "options": RELEVANCE_OPTIONS,
        },
        {
            "fieldname": "strategy_takeaway",
            "fieldtype": "Small Text",
            "label": "What Is One Strategy or Idea You've Taken Away That You Will Use in Your Classroom?",
        },
        {
            "fieldname": "confidence_after_training",
            "fieldtype": "Select",
            "label": "Do You Feel More Confident Supporting Pupils' Resilience and Emotional Regulation After This Training?",
            "options": CONFIDENCE_AFTER_OPTIONS,
        },
        {
            "fieldname": "session_pace",
            "fieldtype": "Select",
            "label": "Was the Length and Pace of the Session Right for You?",
            "options": PACE_OPTIONS,
        },
        {
            "fieldname": "resources_usefulness",
            "fieldtype": "Select",
            "label": "How Useful Were the Resources and Examples Provided?",
            "options": RATING_OPTIONS,
        },
        {
            "fieldname": "future_topics",
            "fieldtype": "Small Text",
            "label": "What Other Topics Would You Like Covered in Future Training?",
        },
        {
            "fieldname": "would_recommend",
            "fieldtype": "Select",
            "label": "Would You Recommend This Training to a Colleague?",
            "options": RECOMMEND_OPTIONS,
        },
        {
            "fieldname": "trainer_feedback",
            "fieldtype": "Small Text",
            "label": "Would You Like to Give Your Trainer Any Feedback?",
        },
        {
            "fieldname": "other_comments",
            "fieldtype": "Small Text",
            "label": "Any Other Comments or Suggestions?",
        },
        {
            "fieldname": "anonymity_consent",
            "fieldtype": "Select",
            "label": "Anonymity",
            "options": ANONYMITY_OPTIONS,
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
        "title": "The Resilient Schools CPD Training - Staff Feedback Form",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": INTRODUCTION_TEXT,
        "button_label": "Submit Feedback",
        "success_title": "Thank you!",
        "success_message": "Your feedback has been received - thank you for taking part.",
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
