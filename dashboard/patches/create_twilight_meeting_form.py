"""
Creates "Twilight Meeting" as a real DocType + Web Form, same pattern as
the other School-branded forms (see create_school_cpd_staff_feedback_form.py).
Deliberately generic - no school name baked into the title/route/intro
text - so the same link can be reused for any school's twilight session,
not just the one it was first requested for. School Name is instead a
field on the form itself, alongside Name and Email.

Plain response capture (round-robin discussion prep, not a scored
assessment) - no field required except the three identity fields
(Name/Email/School Name), matching the source form where only Email was
marked with an asterisk.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Twilight Meeting Response"
WEB_FORM_ROUTE = "twilight-meeting-form"

INTRODUCTION_TEXT = (
    "<p>Ahead of our upcoming twilight session, we'd love to hear from you.</p>"
    "<p>Rather than delivering a traditional training session, we want to make this time "
    "practical, relevant and based on what you are actually seeing with children in school "
    "right now.</p>"
    "<p>The session will be a round-robin style discussion where we explore real situations, "
    "questions and challenges together. We'll look at what might be happening underneath a "
    "child's behaviour and share practical strategies you can take back into the classroom.</p>"
    "<p>There are no right or wrong answers. We want to know what you're finding tricky, what "
    "you've already tried and, importantly, what you'd really like some help with.</p>"
    "<p>Please don't include children's names or any identifying information when sharing "
    "examples.</p>"
    "<p>Your responses will help us shape the session around what you need most.</p>"
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
    return [
        {"fieldname": "form_top_section", "fieldtype": "Section Break"},
        {"fieldname": "full_name", "fieldtype": "Data", "label": "Name", "reqd": 1},
        {"fieldname": "email_address", "fieldtype": "Data", "options": "Email", "label": "Email", "reqd": 1},
        {"fieldname": "school_name", "fieldtype": "Data", "label": "School Name", "reqd": 1},
        {
            "fieldname": "hardest_behaviour",
            "fieldtype": "Small Text",
            "label": "What Behaviour or Situation Are You Finding Hardest to Manage at the Moment?",
            "description": (
                "For example: refusal, anger, anxiety, friendship difficulties, shutdown, "
                "attention-seeking, dysregulation, transitions, separation, not accessing learning."
            ),
        },
        {
            "fieldname": "wish_i_knew",
            "fieldtype": "Small Text",
            "label": 'Complete This Sentence: "I Wish I Knew What to Do When a Child…"',
            "description": "Is there a particular child or situation you would like us to explore?",
        },
        {
            "fieldname": "what_youve_tried",
            "fieldtype": "Small Text",
            "label": "What Have You Already Tried? And What Happened?",
        },
        {
            "fieldname": "child_communicating",
            "fieldtype": "Small Text",
            "label": "What Do You Think the Child Might Be Communicating Through Their Behaviour?",
            "description": "There are no right or wrong answers.",
        },
        {
            "fieldname": "resources_needed",
            "fieldtype": "Small Text",
            "label": "What Resources Would You Benefit From?",
        },
        {
            "fieldname": "question_for_trk",
            "fieldtype": "Small Text",
            "label": "What Is One Question You Would Love to Ask The Resilient Kid Team if You Could Ask Us Anything?",
        },
    ]


def execute():
    try:
        _create_doctype()
        _create_web_form()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_twilight_meeting_form failed")


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
        "title": "Twilight Meeting",
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
        "success_message": "Your responses have been received - thank you for taking the time to share them.",
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
