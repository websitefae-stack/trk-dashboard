"""
Creates "Teacher - Whole-Class Session Feedback Form" as a real
DocType + Web Form, same pattern as the other public feedback forms on
this site (see create_school_cpd_staff_feedback_form.py's own module
docstring). Source: the exact wording/question list Ashley supplied -
no field there was marked as required, so none are required here
either, matching how the other feedback-only (non-consent-gating)
forms on this site are built.

No teacher name/email field - the supplied form doesn't ask for one,
just the session details (School/Year Group/Date/Topic/Coach) and the
feedback questions themselves.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Teacher Session Feedback Response"
WEB_FORM_ROUTE = "teacher-session-feedback"
SCHOOL_DOCTYPE = "School"
COACH_DOCTYPE = "Coach"

RATING_OPTIONS = "1\n2\n3\n4\n5"
RECOMMEND_OPTIONS = "Yes\nMaybe\nNo"
SHARE_CONSENT_OPTIONS = "Yes\nPlease contact the school for permission first\nNo"

INTRODUCTION_TEXT = (
    "<p>Thank you for welcoming us into your classroom!</p>"
    "<p>We would love to hear your feedback on today's session. Your responses help us "
    "understand the impact of our work, celebrate what is working well and identify where "
    "we can offer further support.</p>"
    "<p>This form should take approximately 3 minutes to complete.</p>"
)

SUCCESS_MESSAGE = (
    "<p>Thank you for taking the time to share your feedback.</p>"
    "<p><strong>The Resilient Kid&trade;</strong><br>"
    "Building resilience, one child, one classroom and one connection at a time.</p>"
    "<p><a href=\"https://www.theresilienthub.co.uk\" target=\"_blank\" rel=\"noopener\">"
    "www.theresilienthub.co.uk</a></p>"
)


def _doctype_fields():
    fields = [
        {"fieldname": "about_session_section", "fieldtype": "Section Break", "label": "About the Session"},
        {"fieldname": "year_group_class", "fieldtype": "Data", "label": "Year Group/Class"},
        {"fieldname": "session_date", "fieldtype": "Date", "label": "Date"},
        {"fieldname": "session_topic", "fieldtype": "Data", "label": "Session Topic"},
    ]

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        fields.append({"fieldname": "school", "fieldtype": "Link", "options": SCHOOL_DOCTYPE, "label": "School"})

    if frappe.db.exists("DocType", COACH_DOCTYPE):
        fields.append({"fieldname": "resilience_coach", "fieldtype": "Link", "options": COACH_DOCTYPE, "label": "Resilience Coach"})

    fields += [
        {
            "fieldname": "session_experience_section", "fieldtype": "Section Break",
            "label": "1. Session Experience",
            "description": "Please rate the following from 1-5, where 1 = Poor and 5 = Excellent.",
        },
        {"fieldname": "q1_pupil_engagement", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "How engaged were pupils throughout the session?"},
        {"fieldname": "q2_content_relevance", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "How relevant was the content to the needs of your pupils?"},
        {"fieldname": "q3_key_messages_understood", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "How well did pupils understand the key messages?"},
        {"fieldname": "q4_tools_usefulness", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "How useful were the practical tools and strategies shared?"},
        {"fieldname": "q5_coach_delivery", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "How would you rate the coach's delivery and ability to connect with pupils?"},

        {"fieldname": "learning_impact_section", "fieldtype": "Section Break", "label": "2. Learning and Impact"},
        {"fieldname": "q6_most_valuable_learning", "fieldtype": "Small Text",
         "label": "What was the most valuable thing your pupils learnt from the session?"},
        {"fieldname": "q7_observed_changes", "fieldtype": "Small Text",
         "label": "Did you notice any changes in pupils' confidence, understanding, emotional awareness or "
                  "willingness to participate? Please share any examples."},
        {"fieldname": "q8_tools_continued_use", "fieldtype": "Small Text",
         "label": "Which tools or strategies do you think pupils will continue to use in the classroom or beyond?"},

        {"fieldname": "looking_ahead_section", "fieldtype": "Section Break", "label": "3. Looking Ahead"},
        {"fieldname": "q9_areas_to_explore", "fieldtype": "Small Text",
         "label": "Are there any areas you would like us to explore further with your class?"},
        {"fieldname": "q10_improvement_suggestions", "fieldtype": "Small Text",
         "label": "Is there anything we could do differently to make future sessions even more effective?"},

        {"fieldname": "overall_feedback_section", "fieldtype": "Section Break", "label": "4. Overall Feedback"},
        {"fieldname": "q11_overall_rating", "fieldtype": "Select", "options": RATING_OPTIONS,
         "label": "Overall, how would you rate today's session?"},
        {"fieldname": "q12_recommend", "fieldtype": "Select", "options": RECOMMEND_OPTIONS,
         "label": "Would you recommend The Resilient Kid sessions to another school or teacher?"},
        {"fieldname": "q13_describe_in_words", "fieldtype": "Data",
         "label": "If you could describe today's session in a few words, what would you say?"},

        {"fieldname": "sharing_feedback_section", "fieldtype": "Section Break", "label": "5. Sharing Your Feedback"},
        {"fieldname": "q14_share_consent", "fieldtype": "Select", "options": SHARE_CONSENT_OPTIONS,
         "label": "Are you happy for us to use your feedback anonymously in our reports, case studies or "
                  "promotional materials?"},
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
        "title": "Teacher - Whole-Class Session Feedback Form",
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
        "success_message": SUCCESS_MESSAGE,
        "web_form_fields": _doctype_fields(),
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
