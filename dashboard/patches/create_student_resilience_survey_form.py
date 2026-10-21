"""
Creates the Student Resilience Survey as a real DocType + Web Form, the
same way every other Reports-section "form" on this site already works
(see create_stirling_wellbeing_scale_form.py's own module docstring for
the pattern this follows) - a custom (Desk-style) DocType with a public
Web Form on top, both shipped in this deploy with no manual Desk steps
needed afterwards.

Source: the "Student Resilience Survey" PDF Ashley supplied (a
published Resilience and Youth Development-style instrument) - 40
statements grouped into 6 sections, each answered on a plain 1 (Never)
to 5 (Always) scale, exactly as the original presents it. No scoring
formula was supplied with it (unlike the Stirling scale, which has a
published one), so this only collects the raw per-item answers - it
doesn't invent a composite score for a standardised instrument that
wasn't given one here.

This one is run TWICE per student (before/after), which the Stirling
form never needed to handle - see Ashley's own decision: students are
matched across their two submissions by First/Last Name, not an
anonymous code, since a self-generated code risks a child failing to
reproduce it identically the second time and breaking the pairing. This
is therefore NOT anonymous data the way the Stirling scale is - the raw
DocType stays System Manager only, but coaches and the franchisor DO
see this form's link and results, just never the two name fields: the
generic Forms-module report hides them specifically for this doctype
(see form_reports.py's FORM_HIDDEN_FIELDNAMES), and there's a dedicated
Before/After comparison report (student_resilience_survey.py) that
pairs up each student's two submissions and shows only "Student N",
never a name - see enable_student_resilience_survey_reports_visibility.py
for the follow-up patch that turned this on for the copy already live
before this existed. The school the survey was run at is recorded via
a Link to the existing School doctype (see
create_school_pipeline_doctypes.py) - the school is the Client here,
the individual students never become one.

Runs automatically on the next `bench migrate` (part of a normal
deploy) - no manual step needed.
"""

import frappe

DOCTYPE_NAME = "Student Resilience Survey Response"
WEB_FORM_ROUTE = "student-resilience-survey"
SCHOOL_DOCTYPE = "School"

SCALE_OPTIONS = "1\n2\n3\n4\n5"
SCALE_DESCRIPTION = "1 = Never, 5 = Always"

# (fieldname, statement) - verbatim from the supplied PDF, grouped into
# the same 6 sections it uses. Each section's own lead-in phrase is
# given once as that section's break label, matching how the original
# document presents it (the "..." in each statement continues that
# lead-in).
SECTIONS = [
    (
        "home_adult_section",
        "At home, there is an adult who...",
        [
            ("q1_home_interested_schoolwork", "...is interested in my school work"),
            ("q2_home_believes_success", "...believes that I will be a success"),
            ("q3_home_wants_best", "...wants me to do my best"),
            ("q4_home_listens", "...listens to me when I have something to say"),
        ],
    ),
    (
        "school_adult_section",
        "At school, there is an adult who...",
        [
            ("q5_school_cares", "...really cares about me"),
            ("q6_school_good_job", "...tells me when I do a good job"),
            ("q7_school_listens", "...listens to me when I have something to say"),
            ("q8_school_believes_success", "...believes that I will be a success"),
        ],
    ),
    (
        "away_adult_section",
        "Away from school, there is an adult who...",
        [
            ("q9_away_cares", "...really cares about me"),
            ("q10_away_good_job", "...tells me when I do a good job"),
            ("q11_away_believes_success", "...believes that I will be a success"),
            ("q12_away_trust", "...I trust"),
        ],
    ),
    (
        "away_activities_section",
        "Away from school...",
        [
            ("q13_club_member", "...I am a member of a club, sports team, church group, or other group"),
            ("q14_hobby", "...I take lessons in music, art, sports, or have a hobby"),
        ],
    ),
    (
        "peers_section",
        "Are there students at your school who would...",
        [
            ("q15_peers_choose_team", "...choose you on their team at school"),
            ("q16_peers_explain_rules", "...explain the rules of a game if you didn't understand them"),
            ("q17_peers_invite_home", "...invite you to their home"),
            ("q18_peers_share", "...share things with you"),
            ("q19_peers_help_hurt", "...help you if you hurt yourself"),
            ("q20_peers_miss_you", "...miss you if you weren't at school"),
            ("q21_peers_make_feel_better", "...make you feel better if something is bothering you"),
            ("q22_peers_pick_partner", "...pick you for a partner"),
            ("q23_peers_help_mean", "...help you if other students are being mean to you"),
            ("q24_peers_your_friend", "...tell you you're their friend"),
            ("q25_peers_ask_join", "...ask you to join in when you are all alone"),
            ("q26_peers_tell_secrets", "...tell you secrets"),
        ],
    ),
    (
        "about_you_section",
        "About you",
        [
            ("q27_home_difference", "I do things at home that make a difference (i.e. make things better)"),
            ("q28_help_family_decide", "I help my family make decisions"),
            ("q29_school_decide", "At school, I decide things like class activities or rules"),
            ("q30_school_difference", "I do things at school that make a difference (i.e. make things better)"),
            ("q31_work_out_problems", "I can work out my problems"),
            ("q32_do_most_things", "I can do most things if I try"),
            ("q33_do_well", "There are many things that I do well"),
            ("q34_feel_bad_hurt", "I feel bad when someone gets their feelings hurt"),
            ("q35_understand_feelings", "I try to understand what other people feel"),
            ("q36_find_someone_talk", "When I need help, I find someone to talk to"),
            ("q37_know_where_help", "I know where to go for help when I have a problem"),
            ("q38_talk_through_problems", "I try to work out problems by talking about them"),
            ("q39_goals_future", "I have goals and plans for the future"),
            ("q40_successful_grownup", "I think I will be successful when I grow up"),
        ],
    ),
]


def execute():
    _create_doctype()
    _create_web_form()


def _question_fields():
    fields = []
    for break_fieldname, break_label, questions in SECTIONS:
        fields.append({
            "fieldname": break_fieldname,
            "fieldtype": "Section Break",
            "label": break_label,
            "description": SCALE_DESCRIPTION,
        })
        for fieldname, statement in questions:
            fields.append({
                "fieldname": fieldname,
                "fieldtype": "Select",
                "label": statement,
                "options": SCALE_OPTIONS,
                "reqd": 1,
            })
    return fields


def _create_doctype():
    if frappe.db.exists("DocType", DOCTYPE_NAME):
        return

    fields = [
        {
            "fieldname": "student_first_name",
            "fieldtype": "Data",
            "label": "Student First Name",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "student_last_name",
            "fieldtype": "Data",
            "label": "Student Last Name",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "survey_stage",
            "fieldtype": "Select",
            "label": "Survey Stage",
            "options": "Before\nAfter",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "Lets a Before and After response from the same student be told apart.",
        },
    ]

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        fields.append({
            "fieldname": "school",
            "fieldtype": "Link",
            "label": "School",
            "options": SCHOOL_DOCTYPE,
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        })

    fields.append({
        "fieldname": "questions_section",
        "fieldtype": "Section Break",
        "label": "Responses",
    })
    fields.extend(_question_fields())

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": DOCTYPE_NAME,
        "module": "Dashboard",
        "custom": 1,
        "naming_rule": "Autoincrement",
        "autoname": "autoincrement",
        "fields": fields,
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

    web_form_fields = [
        {
            "fieldname": "student_first_name",
            "fieldtype": "Data",
            "label": "First Name",
            "reqd": 1,
        },
        {
            "fieldname": "student_last_name",
            "fieldtype": "Data",
            "label": "Last Name",
            "reqd": 1,
            "description": "Use the same spelling both times you complete this, so your two surveys can be matched up.",
        },
        {
            "fieldname": "survey_stage",
            "fieldtype": "Select",
            "label": "Is this your Before or After survey?",
            "options": "Before\nAfter",
            "reqd": 1,
        },
    ]

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        web_form_fields.append({
            "fieldname": "school",
            "fieldtype": "Link",
            "label": "School",
            "options": SCHOOL_DOCTYPE,
            "reqd": 1,
        })

    web_form_fields.append({
        "fieldname": "questions_section",
        "fieldtype": "Section Break",
        "label": "Responses",
    })
    web_form_fields.extend(_question_fields())

    doc = frappe.get_doc({
        "doctype": "Web Form",
        "title": "Student Resilience Survey",
        "route": WEB_FORM_ROUTE,
        "doc_type": DOCTYPE_NAME,
        "module": "Dashboard",
        "is_standard": 0,
        "published": 1,
        "login_required": 0,
        "anonymous": 0,
        "introduction_text": (
            "<p>Please read every statement carefully and pick the answer that fits you "
            "best. There are no right or wrong answers.</p>"
        ),
        "button_label": "Submit",
        "success_title": "Thank you!",
        "success_message": "All done - thanks for taking part.",
        "web_form_fields": web_form_fields,
        "custom_show_in_franchisor_reports": 1,
        "custom_show_in_coach_reports": 1,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
