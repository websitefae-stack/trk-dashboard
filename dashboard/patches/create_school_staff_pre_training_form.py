"""
Creates "Resilient Kid - Pre-Training Questionnaire for School Staff" as
a real DocType + Web Form, same pattern as the other School-branded
forms (see create_school_cpd_training_booking_form.py). Fully anonymous
by design (per the source form's own intro) - no name/school/contact
fields at all, matching what was actually asked for.

The two rating-scale questions ("How confident...", "Do you enjoy your
job") are both built as 1-5 scales - the source form had the second one
as 1-10, but Ashley asked to keep every scale question to 5 options
rather than 10, for consistency.

Plain response capture, not a scored assessment - no validate hook
needed. Branded and scoped the same way as the other School forms:
navbar/footer hidden, custom CSS with the School wordmark, School/TRS
Brand Access only.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "School Staff Pre-Training Response"
WEB_FORM_ROUTE = "school-staff-pre-training-questionnaire"

YEAR_GROUP_WORKED_FIELDS = [
    ("year_eyfs", "EYFS"),
    ("year_ks1", "KS1"),
    ("year_ks2", "KS2"),
    ("year_ks3", "KS3"),
    ("year_ks4", "KS4"),
    ("year_ks5", "KS5"),
]

WELLBEING_DESCRIPTION_OPTIONS = "\n".join([
    "Very resilient and emotionally well",
    "Generally okay, with occasional challenges",
    "Mixed - some children are really struggling",
    "Quite a few children are finding things difficult",
    "Overall, resilience and wellbeing feel low",
])

CLASSROOM_ISSUES_FIELDS = [
    ("issue_anxiety_worry", "Anxiety or Worry"),
    ("issue_anger_outbursts", "Anger or Emotional Outbursts"),
    ("issue_friendship_social", "Friendship Issues / Social Struggles"),
    ("issue_low_confidence", "Low Confidence or Self-Esteem"),
    ("issue_managing_change", "Difficulty Managing Change or Transitions"),
    ("issue_concentration_motivation", "Poor Concentration or Motivation"),
    ("issue_behaviour_distress", "Behaviour That Communicates Distress"),
]

STAFF_CHALLENGES_FIELDS = [
    ("challenge_workload", "Workload/Time Pressure"),
    ("challenge_emotional_fatigue", "Emotional Fatigue/Burnout"),
    ("challenge_managing_behaviour", "Managing Behaviour or Dysregulation"),
    ("challenge_complex_needs", "Supporting Complex Needs"),
    ("challenge_undervalued", "Feeling Undervalued or Unseen"),
    ("challenge_communication_teamwork", "Communication or Teamwork Challenges"),
]

TRAINING_GOALS_FIELDS = [
    ("goal_practical_strategies", "Practical Classroom Strategies"),
    ("goal_understanding_brains", "Understanding Children's Brains and Behaviour"),
    ("goal_building_resilience", "Tools for Building Resilience in Pupils"),
    ("goal_own_wellbeing", "Support for My Own Wellbeing"),
    ("goal_share_with_others", "Ideas to Share with Colleagues or Parents"),
]

CONFIDENCE_OPTIONS = "1 - Not At All Confident\n2\n3\n4\n5 - Very Confident"
ENJOYMENT_OPTIONS = "1 - Not At All\n2\n3\n4\n5 - I Love It"
YES_NO_OPTIONS = "Yes\nNo"

INTRODUCTION_TEXT = (
    "<p>This questionnaire is anonymous. Your honest responses will help us tailor the "
    "training to your setting and support both staff and students more effectively.</p>"
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
        {
            "fieldname": "about_you_section",
            "fieldtype": "Section Break",
            "label": "What year group(s) do you currently work with?",
        },
    ]

    for fieldname, label in YEAR_GROUP_WORKED_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {
            "fieldname": "support_role",
            "fieldtype": "Data",
            "label": "Support Role",
            "description": "e.g. SEN, pastoral, TA, wellbeing, etc.",
        },
        {"fieldname": "pupil_wellbeing_section", "fieldtype": "Section Break", "label": "Pupil Wellbeing"},
        {
            "fieldname": "pupil_wellbeing_description",
            "fieldtype": "Select",
            "label": "How would you describe the general wellbeing or emotional resilience of the pupils you work with?",
            "options": WELLBEING_DESCRIPTION_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "classroom_issues_label",
            "fieldtype": "Section Break",
            "label": "What are the most common issues you're seeing in the classroom?",
            "description": "Please tick up to three that feel most relevant.",
        },
    ]

    for fieldname, label in CLASSROOM_ISSUES_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields.append({
        "fieldname": "classroom_issues_other",
        "fieldtype": "Data",
        "label": "Other (please specify)",
    })

    fields += [
        {"fieldname": "staff_wellbeing_section", "fieldtype": "Section Break", "label": "Staff Wellbeing"},
    ]

    for fieldname, label in STAFF_CHALLENGES_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {
            "fieldname": "training_goals_section",
            "fieldtype": "Section Break",
            "label": "What would you most like to gain from this training?",
        },
    ]

    for fieldname, label in TRAINING_GOALS_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields.append({
        "fieldname": "training_goals_other",
        "fieldtype": "Data",
        "label": "Other (please specify)",
    })

    fields += [
        {
            "fieldname": "behaviour_times_of_day",
            "fieldtype": "Small Text",
            "label": "Are there particular times of day when difficulties in behaviour tend to increase?",
            "reqd": 1,
        },
        {"fieldname": "confidence_section", "fieldtype": "Section Break", "label": "Confidence & Reflection"},
        {
            "fieldname": "confidence_supporting_dysregulated",
            "fieldtype": "Select",
            "label": "How confident do you currently feel supporting children who are dysregulated or anxious?",
            "options": CONFIDENCE_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "calming_strategies_used",
            "fieldtype": "Small Text",
            "label": "Which regulation or calming strategies do you already use?",
            "reqd": 1,
        },
        {
            "fieldname": "job_enjoyment",
            "fieldtype": "Select",
            "label": "Do you enjoy your job?",
            "options": ENJOYMENT_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "what_makes_you_come_to_work",
            "fieldtype": "Small Text",
            "label": "What makes you want to come to work?",
            "reqd": 1,
        },
        {
            "fieldname": "thought_about_leaving",
            "fieldtype": "Select",
            "label": "Have you ever thought about leaving teaching?",
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },
        {"fieldname": "closing_section", "fieldtype": "Section Break", "label": "Anything Else"},
        {
            "fieldname": "additional_information",
            "fieldtype": "Small Text",
            "label": "Is there anything else you'd like the trainer to know ahead of the session?",
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
        "title": "Pre-Training Questionnaire for School Staff",
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
        "success_message": "Thanks for sharing - your answers will help shape the training.",
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
