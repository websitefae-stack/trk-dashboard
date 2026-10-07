"""
Creates "Reference Questionnaire" as a real DocType + Web Form, same
pattern as the other School-branded forms (see
create_school_cpd_staff_feedback_form.py). A referee-facing safeguarding
reference, reused as-is for BOTH a Sessional Worker applicant and a
prospective Franchisee (Ashley's own call - one generic reference link
covers both pipelines rather than maintaining near-duplicate forms) -
not tied to any one applicant/pipeline by name, so the same link is
reusable for every reference request regardless of which role the
applicant is being considered for. Written in the second person
throughout ("Your Name", "Your Job Title") since the person filling
this in IS the referee, not a third party describing one.

Question 3 ("Professional qualities") is a rating-grid in the source
Google Form (10 rows x Excellent/Good/Satisfactory/Unable to Comment) -
this codebase has no grid/matrix field type on guest Web Forms (see
create_school_cpd_staff_feedback_form.py's own MODULE_FIELDS pattern),
so it's built the same established way: one Select field per row, all
sharing the same PROFESSIONAL_QUALITIES_OPTIONS scale, stacked under one
Section Break heading.

Safeguarding-sensitive (this is a reference check on someone applying to
work with children), so only visible in franchisor reports, not coach
reports - unlike most other standalone forms here.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Sessional Worker Reference Response"
WEB_FORM_ROUTE = "sessional-worker-reference-form"

YES_NO_OPTIONS = "Yes\nNo"

PROFESSIONAL_QUALITIES_OPTIONS = "Excellent\nGood\nSatisfactory\nUnable to Comment"
PROFESSIONAL_QUALITIES = [
    ("rating_reliability_punctuality", "Reliability and Punctuality"),
    ("rating_communication", "Communication"),
    ("rating_professional_boundaries", "Professional Boundaries"),
    ("rating_build_relationships", "Ability to Build Relationships"),
    ("rating_empathy_understanding", "Empathy and Understanding"),
    ("rating_work_independently", "Ability to Work Independently"),
    ("rating_work_as_team", "Ability to Work as Part of a Team"),
    ("rating_challenging_situations", "Responding Appropriately to Challenging Situations"),
    ("rating_confidentiality_discretion", "Confidentiality and Discretion"),
    ("rating_professionalism", "Professionalism"),
]

RECOMMEND_OPTIONS = (
    "Yes, without reservation\n"
    "Yes\n"
    "Yes, with some reservations - please explain below\n"
    "No\n"
    "Unable to comment"
)

DECLARATION_OPTIONS = (
    "I confirm that the information provided is accurate to the best of my knowledge\n"
    "I do not confirm the information provided is accurate to the best of my knowledge"
)

INTRODUCTION_TEXT = (
    "<p>Thank you for agreeing to provide a reference for the above applicant, who is being "
    "considered for a role with The Resilient Kid - either as a Sessional Worker or as a "
    "Franchisee - that involves direct contact with children and young people.</p>"
    "<p>We would be grateful if you could answer the following questions as fully and "
    "honestly as possible.</p>"
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
        {"fieldname": "email_address", "fieldtype": "Data", "options": "Email", "label": "Email", "reqd": 1},
        {"fieldname": "applicant_name", "fieldtype": "Data", "label": "Applicant's Name", "reqd": 1},
        {"fieldname": "referee_name", "fieldtype": "Data", "label": "Your Name", "reqd": 1},
        {"fieldname": "referee_job_title", "fieldtype": "Data", "label": "Your Job Title", "reqd": 1},
        {"fieldname": "organisation", "fieldtype": "Data", "label": "Organisation", "reqd": 1},
        {"fieldname": "telephone", "fieldtype": "Data", "label": "Telephone", "reqd": 1},

        {
            "fieldname": "relationship_section",
            "fieldtype": "Section Break",
            "label": "1. Your Relationship With the Applicant",
        },
        {
            "fieldname": "how_long_known",
            "fieldtype": "Data",
            "label": "How Long Have You Known the Applicant?",
        },
        {
            "fieldname": "role_and_dates",
            "fieldtype": "Small Text",
            "label": "If You Employed or Supervised Them, Please Confirm Their Role and Approximate Dates",
        },

        {
            "fieldname": "working_with_children_section",
            "fieldtype": "Section Break",
            "label": "2. Working With Children and Young People",
        },
        {
            "fieldname": "observed_working_with_children",
            "fieldtype": "Select",
            "label": "Have You Observed the Applicant Working With Children or Young People?",
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "nature_of_work",
            "fieldtype": "Small Text",
            "label": "If Yes, Please Briefly Describe the Nature of This Work",
        },

        {
            "fieldname": "professional_qualities_section",
            "fieldtype": "Section Break",
            "label": "3. Professional Qualities",
        },
    ]

    for fieldname, label in PROFESSIONAL_QUALITIES:
        fields.append({
            "fieldname": fieldname,
            "fieldtype": "Select",
            "label": label,
            "options": PROFESSIONAL_QUALITIES_OPTIONS,
            "reqd": 1,
        })

    fields += [
        {
            "fieldname": "safeguarding_section",
            "fieldtype": "Section Break",
            "label": "4. Safeguarding and Suitability",
        },
        {
            "fieldname": "suitability_concerns",
            "fieldtype": "Select",
            "label": (
                "To the Best of Your Knowledge, Do You Have Any Concerns About This "
                "Person's Suitability to Work With Children or Young People?"
            ),
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "suitability_concerns_details",
            "fieldtype": "Small Text",
            "label": "If Yes, Please Provide Further Information",
        },
        {
            "fieldname": "safeguarding_concerns",
            "fieldtype": "Select",
            "label": "Are You Aware of Any Safeguarding Concerns or Allegations Relating to Their Conduct With Children or Vulnerable People?",
            "description": "Including any disciplinary matters.",
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },

        {
            "fieldname": "overall_reference_section",
            "fieldtype": "Section Break",
            "label": "5. Overall Reference",
        },
        {
            "fieldname": "main_strengths",
            "fieldtype": "Small Text",
            "label": (
                "What Would You Consider to Be the Applicant's Main Strengths When Working "
                "With Children, Young People, Families or Professionals?"
            ),
            "reqd": 1,
        },
        {
            "fieldname": "additional_support_needed",
            "fieldtype": "Small Text",
            "label": (
                "Is There Anything You Feel We Should Be Aware Of, or Any Area in Which "
                "They May Require Additional Support, Training or Supervision?"
            ),
        },
        {
            "fieldname": "recommend_suitable",
            "fieldtype": "Select",
            "label": "Would You Recommend This Person as Suitable to Work With Children and Young People Within The Resilient Kid?",
            "options": RECOMMEND_OPTIONS,
            "reqd": 1,
        },
        {
            "fieldname": "reservations_explanation",
            "fieldtype": "Small Text",
            "label": "If You Have Reservations, Please Explain",
        },
        {
            "fieldname": "would_work_with_again",
            "fieldtype": "Select",
            "label": "Would You Employ or Work With This Person Again?",
            "options": YES_NO_OPTIONS,
            "reqd": 1,
        },

        {"fieldname": "declaration_section", "fieldtype": "Section Break", "label": "Declaration"},
        {
            "fieldname": "declaration",
            "fieldtype": "Select",
            "label": "Declaration",
            "options": DECLARATION_OPTIONS,
            "reqd": 1,
        },
        {"fieldname": "signed_date", "fieldtype": "Date", "label": "Date", "reqd": 1},
    ]

    return fields


def execute():
    try:
        _create_doctype()
        _create_web_form()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_sessional_worker_reference_form failed")


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
        "title": "Reference Questionnaire",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": INTRODUCTION_TEXT,
        "button_label": "Submit Reference",
        "success_title": "Thank you!",
        "success_message": "Thank you for taking the time to complete this reference.",
        "web_form_fields": _doctype_fields(),
        "hide_navbar": 1,
        "hide_footer": 1,
        "custom_css": CUSTOM_CSS,
        # Safeguarding-sensitive reference check on a job applicant -
        # franchisor visibility only, unlike most other standalone forms
        # here which also show in coach reports.
        "custom_show_in_franchisor_reports": 1,
        "custom_brand_access_school": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
