"""
Creates "Staff Reflection Session - Pre-Session Questionnaire" as a real
DocType + Web Form, same pattern as the other School-branded forms (see
create_school_staff_pre_training_form.py) - built from the PDF Ashley
uploaded. Fully anonymous by design (per the source PDF's own intro) -
no name/school/contact fields at all.

module is read off an existing, already-correctly-discovered Forms
doctype (Sessional Worker Reference Response) rather than hardcoded -
every other create_*_form.py patch in this repo writes "module":
"Dashboard" literally, which was that module's name at the time each
one ran; copying a live value sidesteps needing to know what it's
actually named today.

Runs automatically on the next `bench migrate` - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Staff Reflection Session Response"
WEB_FORM_ROUTE = "staff-reflection-session-questionnaire"
REFERENCE_DOCTYPE_FOR_MODULE = "Sessional Worker Reference Response"

ROLE_OPTIONS = "\n".join([
    "Class Teacher",
    "Teaching Assistant / Learning Support",
    "SENCo / Inclusion Team",
    "Senior Leadership",
    "Other",
])

PHASE_OPTIONS = "\n".join([
    "EYFS", "KS1", "Lower KS2", "Upper KS2", "Across the School",
])

CONFIDENCE_OPTIONS = "1 - Not At All Confident\n2\n3\n4\n5 - Very Confident"

THEME_GROUPS = [
    ("Emotional Wellbeing and Regulation", [
        ("theme_big_emotions", "Children who struggle to manage big emotions (anger, upset, frustration)"),
        ("theme_anxiety_worry", "Anxiety, worry and school-based anxiety"),
        ("theme_low_self_esteem", "Low self-esteem and confidence"),
        ("theme_withdraw_quiet", "Children who withdraw or go quiet"),
        ("theme_transitions", "Supporting children through transitions (new class, new school, moving to secondary)"),
    ]),
    ("Behaviour and Relationships", [
        ("theme_dysregulated_behaviour", "Dysregulated or challenging behaviour"),
        ("theme_friendship_difficulties", "Friendship difficulties and fallouts"),
        ("theme_unkind_bullying", "Unkind behaviour, exclusion and bullying"),
        ("theme_repairing_relationships", "Repairing relationships after an incident"),
        ("theme_belonging", "Building a sense of belonging in the class"),
    ]),
    ("SEND and Neurodiversity", [
        ("theme_autistic_pupils", "Supporting autistic pupils"),
        ("theme_adhd", "Supporting pupils with ADHD"),
        ("theme_sensory_needs", "Sensory needs in the classroom"),
        ("theme_awaiting_assessment", "Children awaiting assessment or diagnosis"),
        ("theme_adapting_expectations", "Adapting expectations without lowering them"),
    ]),
    ("Home and Life Outside School", [
        ("theme_bereavement", "Bereavement, loss and separation"),
        ("theme_family_changes", "Family changes or difficulties at home"),
        ("theme_working_with_parents", "Working with parents and carers, including difficult conversations"),
        ("theme_attendance_avoidance", "Attendance and emotionally based school avoidance"),
    ]),
    ("Online World", [
        ("theme_online_safety_gaming", "Online safety and gaming"),
        ("theme_social_media_fallouts", "Social media, group chats and online fallouts"),
        ("theme_worrying_online_content", "Worrying things children have seen or heard online"),
    ]),
    ("Safeguarding and Disclosures", [
        ("theme_responding_disclosure", "Feeling confident responding to a disclosure"),
    ]),
    ("Staff Wellbeing", [
        ("theme_emotional_impact_job", "Managing the emotional impact of the job"),
        ("theme_support_after_incident", "Feeling supported after a difficult incident"),
        ("theme_balancing_needs", "Balancing the needs of one child with the needs of the whole class"),
    ]),
]

SUPPORT_FIELDS = [
    ("support_knowing_what_to_say", "Knowing what to say and what not to say in the moment"),
    ("support_after_passing_concern", "What happens after you pass a concern on"),
    ("support_emotional_impact", "Managing the emotional impact of the job"),
    ("support_after_difficult_incident", "Feeling supported after a difficult incident"),
    ("support_balancing_needs", "Balancing the needs of one child with the needs of the whole class"),
    ("support_practical_strategies", "Practical classroom strategies"),
    ("support_time_with_colleagues", "Time to talk with colleagues"),
    ("support_training_cpd", "Training or CPD on a specific topic"),
    ("support_resources_classroom", "Resources for the classroom (visuals, calm corner, sensory items)"),
    ("support_clearer_processes", "Clearer processes for getting help"),
    ("support_check_ins", "Check-ins after difficult incidents"),
]

INTRODUCTION_TEXT = (
    "<p>Thank you for taking a few minutes to complete this questionnaire. It will help shape our "
    "one-hour session so that we spend the time on the things that matter most to you in the classroom.</p>"
    "<p><strong>Confidentiality:</strong> Everything you write here, and everything shared during the "
    "session, is confidential. Your answers will not be shared with anyone outside the session, and no "
    "individual staff member, pupil, family or class will be identified. Only general themes will be "
    "discussed outside the session, for example to help plan future support or training.</p>"
    "<p>Please do not use the names of pupils, families or colleagues in your answers. You can describe a "
    "situation in general terms instead (for example, \"a pupil in Year 3 who…\").</p>"
    "<p>You do not have to answer every question. Answer as much or as little as feels comfortable.</p>"
    "<p><em>If anything in this questionnaire raises a safeguarding concern, please speak to the "
    "Designated Safeguarding Lead straight away rather than waiting for the session.</em></p>"
)


def _doctype_fields():
    fields = [
        {
            "fieldname": "about_you_section",
            "fieldtype": "Section Break",
            "label": "About You (Optional)",
        },
        {
            "fieldname": "staff_role",
            "fieldtype": "Select",
            "label": "Your Role",
            "options": ROLE_OPTIONS,
        },
        {
            "fieldname": "staff_role_other",
            "fieldtype": "Data",
            "label": "Other Role (please specify)",
        },
        {
            "fieldname": "phase",
            "fieldtype": "Select",
            "label": "Which Phase Do You Mainly Work In?",
            "options": PHASE_OPTIONS,
        },
        {
            "fieldname": "themes_section",
            "fieldtype": "Section Break",
            "label": "Themes You Would Like to Discuss",
            "description": "Please tick any you would find helpful to talk about in the session.",
        },
    ]

    for group_label, items in THEME_GROUPS:
        fields.append({"fieldname": "themes_group_" + group_label.lower().replace(" ", "_"), "fieldtype": "Section Break", "label": group_label})
        for fieldname, label in items:
            fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {
            "fieldname": "themes_other",
            "fieldtype": "Small Text",
            "label": "Are there any other themes you would like to add?",
        },
        {"fieldname": "experience_section", "fieldtype": "Section Break", "label": "Your Experience in Class"},
        {
            "fieldname": "common_challenge",
            "fieldtype": "Small Text",
            "label": "What is the most common challenge you face in your classroom at the moment?",
            "description": "Please describe in general terms, without names.",
        },
        {
            "fieldname": "difficult_situation",
            "fieldtype": "Small Text",
            "label": "Is there a situation you have found difficult to know how to respond to, that you would value talking through with colleagues?",
        },
        {
            "fieldname": "what_working_well",
            "fieldtype": "Small Text",
            "label": "What is working well for you? Is there a strategy, routine or approach you would be happy to share with others?",
        },
        {"fieldname": "confidence_section", "fieldtype": "Section Break", "label": "Confidence and Support"},
        {
            "fieldname": "confidence_emotional_wellbeing",
            "fieldtype": "Select",
            "label": "How confident do you feel supporting children's emotional wellbeing in class?",
            "options": CONFIDENCE_OPTIONS,
        },
        {
            "fieldname": "confidence_dysregulated_behaviour",
            "fieldtype": "Select",
            "label": "How confident do you feel managing dysregulated behaviour?",
            "options": CONFIDENCE_OPTIONS,
        },
        {
            "fieldname": "support_needed_section",
            "fieldtype": "Section Break",
            "label": "What Would Help You Feel More Supported?",
            "description": "Tick any that apply.",
        },
    ]

    for fieldname, label in SUPPORT_FIELDS:
        fields.append({"fieldname": fieldname, "fieldtype": "Check", "label": label})

    fields += [
        {
            "fieldname": "support_needed_other",
            "fieldtype": "Data",
            "label": "Other (please specify)",
        },
        {"fieldname": "session_section", "fieldtype": "Section Break", "label": "The Session"},
        {
            "fieldname": "session_worthwhile",
            "fieldtype": "Small Text",
            "label": "What would make this hour feel worthwhile for you?",
        },
        {
            "fieldname": "prefer_not_discuss",
            "fieldtype": "Small Text",
            "label": "Is there anything you would prefer not to discuss as a group, or would rather raise privately?",
        },
    ]

    return fields


def _resolve_module():
    return frappe.db.get_value("DocType", REFERENCE_DOCTYPE_FOR_MODULE, "module") or "Dashboard"


def execute():
    if not frappe.db.exists("DocType", REFERENCE_DOCTYPE_FOR_MODULE):
        return

    _create_doctype()
    _create_web_form()


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": _resolve_module(),
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
        "title": "Staff Reflection Session - Pre-Session Questionnaire",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": _resolve_module(),
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 1,
        "introduction_text": INTRODUCTION_TEXT,
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": (
            "Thank you for your honesty and for everything you do for the children in your care. "
            "Your responses will be used only to plan the session."
        ),
        "web_form_fields": _doctype_fields(),
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 1,
        "custom_brand_access_school": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
