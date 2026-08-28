"""
"Forms" report for the Reports section: Intake Forms (Client Lead's
intake questionnaire) plus every DocType in the site's "Forms" module
(Desk-built feedback/survey forms, discovered from Frappe's own DocType
metadata rather than a hardcoded list - see get_form_module_doctypes()).
Scoped the same way every other list in this app is - coaches see their
own, franchisors see everyone's. Read-only summaries that link out to the
existing lead/client detail pages rather than duplicating their full
answer rendering here.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import (
    ensure_logged_in,
    is_franchisor_user,
    get_current_coach_name,
    get_allowed_client_names,
    CLIENT_DOCTYPE,
)
from dashboard.api.shared.leads import (
    LEAD_DOCTYPE,
    ensure_lead_access,
    get_intake_question_fields,
    get_intake_field_value,
)
from dashboard.api.shared.clients import get_coach_label

FORMS_MODULE = "Forms"

_FORM_SKIP_FIELDTYPES = {
    "Section Break", "Column Break", "Table", "HTML", "Button", "Tab Break",
    "Table MultiSelect", "Fold", "Heading",
}
_FORM_SKIP_FIELDNAMES = {"naming_series", "amended_from"}


def _lead_filters_for_forms_report():
    """
    None means "no filter" (franchisor sees every lead's intake form). Any
    other value restricts to the current coach's own leads.

    Deliberately does NOT accept a dashboard_type argument from the
    caller - is_franchisor_user() is derived purely from
    frappe.session.user, so a client-supplied "dashboard_type": "franchisor"
    can never widen what this returns. (leads.py's own equivalent helper
    ORs in a caller-supplied dashboard_type; not copied here on purpose,
    since intake answers include contact details and this report has no
    legitimate reason to trust anything from the request body for that
    decision.)
    """
    ensure_logged_in()

    if is_franchisor_user():
        return None

    coach_name = get_current_coach_name(optional=True)

    if not coach_name:
        return {"name": ["in", []]}

    return {"coach": coach_name}


@frappe.whitelist()
def get_intake_form_report(from_date=None, to_date=None):
    ensure_logged_in()

    filters = _lead_filters_for_forms_report()
    filters = dict(filters) if filters else {}
    filters["intake_sent_on"] = ["is", "set"]

    if from_date or to_date:
        filters["intake_sent_on"] = [
            "between",
            [f"{from_date} 00:00:00" if from_date else "1970-01-01 00:00:00",
             f"{to_date} 23:59:59" if to_date else frappe.utils.now()],
        ]

    rows = frappe.get_all(
        LEAD_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "client_name",
            "contact_name",
            "contact_email",
            "coach",
            "client_type",
            "status",
            "intake_sent_on",
            "intake_completed_on",
        ],
        limit_page_length=2000,
        ignore_permissions=True,
    )

    # frappe.get_all()'s order_by validation rejects raw SQL like
    # coalesce(...) (only 'field', 'link_field.field', 'child_table.field'
    # are allowed), so the "completed date, falling back to sent date" sort
    # is done here instead.
    rows.sort(key=lambda row: row.get("intake_completed_on") or row.get("intake_sent_on"), reverse=True)

    for row in rows:
        row["coach_label"] = get_coach_label(row.get("coach"))
        row["is_completed"] = 1 if row.get("intake_completed_on") else 0

    return rows


@frappe.whitelist()
def get_intake_form_questions():
    """
    Every "question" the intake form can be broken down by - powers the
    Reports section's "one question - everyone's answer" view. No access
    check beyond being logged in: this only lists field labels, never
    answer data.
    """
    ensure_logged_in()

    return [
        {"value": "client_name", "label": "Client Name"},
        {"value": "contact_name", "label": "Contact Name"},
    ] + [
        {"value": df.fieldname, "label": df.label or df.fieldname}
        for df in get_intake_question_fields()
    ]


@frappe.whitelist()
def get_intake_form_answers_for_person(name=None):
    """One lead's full set of intake answers - the "one specific person" view."""
    doc = ensure_lead_access(name)

    if not doc.get("intake_sent_on"):
        frappe.throw(_("This lead has no intake form."))

    answers = [{"label": "Client Name", "value": doc.client_name}, {"label": "Contact Name", "value": doc.contact_name}]
    answers += [
        {"label": df.label or df.fieldname, "value": get_intake_field_value(doc, df)}
        for df in get_intake_question_fields()
        if get_intake_field_value(doc, df) is not None
    ]

    return {
        "name": doc.name,
        "client_name": doc.client_name,
        "contact_name": doc.contact_name,
        "coach_label": get_coach_label(doc.coach),
        "answers": answers,
    }


@frappe.whitelist()
def get_intake_form_answers_for_question(question=None):
    """Every accessible lead's answer to one specific intake question."""
    ensure_logged_in()

    question = (question or "").strip()
    if not question:
        frappe.throw(_("Select a question."))

    label = question
    df = None

    if question in ("client_name", "contact_name"):
        label = "Client Name" if question == "client_name" else "Contact Name"
    else:
        # Only fields get_intake_form_questions() actually offered - not any
        # arbitrary Lead fieldname (e.g. the internal "status"/"coach"/
        # "source" fields _INTAKE_PDF_SKIP_FIELDS deliberately excludes from
        # "questions").
        matching = [f for f in get_intake_question_fields() if f.fieldname == question]
        if not matching:
            frappe.throw(_("Unknown question."))
        df = matching[0]
        label = df.label or question

    filters = _lead_filters_for_forms_report()
    filters = dict(filters) if filters else {}
    filters["intake_sent_on"] = ["is", "set"]

    lead_names = frappe.get_all(
        LEAD_DOCTYPE, filters=filters, pluck="name", limit_page_length=2000, ignore_permissions=True
    )

    rows = []
    for lead_name in lead_names:
        doc = frappe.get_doc(LEAD_DOCTYPE, lead_name)
        value = doc.get(question) if df is None else get_intake_field_value(doc, df)

        rows.append({
            "lead": lead_name,
            "client_name": doc.client_name,
            "coach_label": get_coach_label(doc.coach),
            "value": value or "",
        })

    return {"question": label, "rows": rows}


def _form_visibility(doctype):
    """
    The Form Visibility Rule (a self-service settings list office
    maintains in Desk) value for this form, or "Everyone" if it isn't
    listed there at all - including when the rule DocType doesn't exist
    yet (pre-migration), treated the same as "no rules configured".
    """
    if not frappe.db.exists("DocType", "Form Visibility Rule"):
        return "Everyone"

    return frappe.db.get_value("Form Visibility Rule", doctype, "visibility") or "Everyone"


def _is_form_restricted_to_franchisors(doctype):
    return _form_visibility(doctype) == "Franchisors Only"


def _is_form_restricted_to_coaches(doctype):
    return _form_visibility(doctype) == "Coaches Only"


def _is_form_hidden(doctype):
    return _form_visibility(doctype) == "Hidden"


def _form_doctype_meta(doctype):
    """
    Validates that `doctype` is a real, non-child, non-single DocType in
    the Forms module before ever touching its data - the only thing a
    caller can pick is one of the names get_form_module_doctypes() itself
    offered, never an arbitrary doctype name. Also independently enforces
    Form Visibility Rule here (not just in get_form_module_doctypes()'s
    picker) - every other function in this module (get_form_charts,
    get_form_report, get_form_submission, etc.) routes through this, so a
    coach can't bypass a "Franchisors Only" rule (or a franchisor bypass
    a "Coaches Only" one) just by calling the API directly with the
    doctype name the UI never offered them.
    """
    doctype = (doctype or "").strip()
    if not doctype:
        frappe.throw(_("Select a form."))

    row = frappe.db.get_value("DocType", doctype, ["module", "istable", "issingle"], as_dict=True)

    if not row or row.module != FORMS_MODULE or row.istable or row.issingle:
        frappe.throw(_("Unknown form."))

    if _is_form_hidden(doctype):
        frappe.throw(_("Unknown form."))

    if is_franchisor_user():
        if _is_form_restricted_to_coaches(doctype):
            frappe.throw(_("You do not have permission to view this form."), frappe.PermissionError)
    elif _is_form_restricted_to_franchisors(doctype):
        frappe.throw(_("You do not have permission to view this form."), frappe.PermissionError)

    return frappe.get_meta(doctype)


def _form_question_fields(meta):
    return [
        df for df in meta.fields
        if df.fieldtype not in _FORM_SKIP_FIELDTYPES and df.fieldname not in _FORM_SKIP_FIELDNAMES
    ]


def _form_link_field(meta):
    """
    The field a submission is tied to a person by, if any - the first
    Link field pointing at Client or Client Lead. Many forms are set up
    anonymous with no such field at all, in which case submissions can't
    be attributed to anyone (or scoped to a particular coach's clients -
    see _form_scope_filter_value()).
    """
    for df in meta.fields:
        if df.fieldtype == "Link" and df.options in (CLIENT_DOCTYPE, LEAD_DOCTYPE):
            return df
    return None


def _form_field_value(row, df):
    value = row.get(df.fieldname)

    if df.fieldtype == "Check":
        return "Yes" if value else None
    if df.fieldtype == "Rating":
        if not value:
            return None
        stars = _rating_star_count(value, df)
        return f"{stars} Star" + ("" if stars == 1 else "s")
    if df.fieldtype == "Date" and value:
        return frappe.utils.formatdate(value, "dd-MM-yyyy")
    if df.fieldtype == "Datetime" and value:
        return frappe.utils.format_datetime(value, "dd-MM-yyyy HH:mm")

    return value or None


def _form_person_label(link_doctype, name):
    if not name:
        return "Anonymous"

    if link_doctype == CLIENT_DOCTYPE:
        return _client_display_name(name) or name

    if link_doctype == LEAD_DOCTYPE:
        row = frappe.db.get_value(LEAD_DOCTYPE, name, ["client_name", "contact_name"], as_dict=True)
        if row:
            return row.get("client_name") or row.get("contact_name") or name

    return name


def _form_coach_label(link_doctype, name):
    if not name:
        return ""

    if link_doctype == CLIENT_DOCTYPE:
        return _coach_label_for_client(name)

    if link_doctype == LEAD_DOCTYPE:
        return get_coach_label(frappe.db.get_value(LEAD_DOCTYPE, name, "coach"))

    return ""


def _form_scope_filter_value(link_field):
    """
    None means no restriction is applied - either a franchisor/office
    login (sees every submission), or a form with no Client/Client Lead
    link field at all (an anonymous form's submissions aren't attributable
    to any particular coach's clients, so there's nothing meaningful to
    scope by - every logged-in user sees the same anonymous aggregate).
    Otherwise an ["in", [...]] filter value for the link field, restricting
    to the current coach's own clients/leads.
    """
    if not link_field or is_franchisor_user():
        return None

    if link_field.options == CLIENT_DOCTYPE:
        names = get_allowed_client_names()
    elif link_field.options == LEAD_DOCTYPE:
        coach_name = get_current_coach_name(optional=True)
        names = (
            frappe.get_all(LEAD_DOCTYPE, filters={"coach": coach_name}, pluck="name", limit_page_length=5000)
            if coach_name else []
        )
    else:
        return None

    return ["in", names]


def _form_date_range_filters(from_date, to_date):
    if not (from_date or to_date):
        return {}

    return {
        "creation": [
            "between",
            [f"{from_date} 00:00:00" if from_date else "1970-01-01 00:00:00",
             f"{to_date} 23:59:59" if to_date else frappe.utils.now()],
        ]
    }


_CHART_CATEGORICAL_FIELDTYPES = {"Select", "Check", "Rating"}
_CHART_MAX_LINK_CATEGORIES = 12


def _rating_star_count(value, df):
    """
    Rating fields store a 0-1 fraction of the field's configured max stars
    (df.options holds that max, as a string - blank/invalid defaults to the
    Frappe standard of 5). Converts back to a whole star count for display.
    """
    max_stars = int(df.options) if (df.options or "").strip().isdigit() else 5
    return round(float(value or 0) * max_stars)


def _chart_field_value(row, df):
    """
    Same idea as _form_field_value(), except a Check field's unanswered
    (falsy) value comes back as an explicit "No" rather than being dropped
    - _form_field_value()'s None-for-unchecked convention exists so a
    label/value list only shows fields someone actually filled in (an
    optional Intake checkbox nobody ticked shouldn't appear at all), but a
    chart needs both buckets of a real Yes/No question counted, not one
    silently vanishing.
    """
    value = row.get(df.fieldname)

    if df.fieldtype == "Check":
        return "Yes" if value else "No"
    if df.fieldtype == "Rating":
        if not value:
            return None
        stars = _rating_star_count(value, df)
        return f"{stars} Star" + ("" if stars == 1 else "s")
    if df.fieldtype == "Date" and value:
        return frappe.utils.formatdate(value, "dd-MM-yyyy")
    if df.fieldtype == "Datetime" and value:
        return frappe.utils.format_datetime(value, "dd-MM-yyyy HH:mm")

    return value or None


def _chart_bucket_for_field(df, doctype, filters):
    """
    Returns ("chart", [{"label", "count", "percent"}, ...]) for a
    categorical question (Select, Check, or a Link with few enough distinct
    values to plot), or ("list", [answer, answer, ...]) for free text (or a
    Link with too many distinct values to chart meaningfully).
    """
    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=[df.fieldname],
        order_by="creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    values = [_chart_field_value(row, df) for row in rows]
    values = [v for v in values if v is not None]

    is_categorical = df.fieldtype in _CHART_CATEGORICAL_FIELDTYPES

    if df.fieldtype == "Link":
        is_categorical = len(set(values)) <= _CHART_MAX_LINK_CATEGORIES

    if not is_categorical:
        return "list", values

    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1

    if df.fieldtype == "Rating":
        # Reads naturally as "1 star, 2 stars, ... 5 stars" left to right
        # instead of jumbled by whichever count happens to be largest.
        def _star_sort_key(item):
            try:
                return int(item[0].split(" ")[0])
            except (ValueError, IndexError):
                return 0

        sorted_items = sorted(counts.items(), key=_star_sort_key)
    else:
        sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)

    total = len(values)
    data = [
        {"label": label, "count": count, "percent": round(count * 100 / total, 1) if total else 0}
        for label, count in sorted_items
    ]

    return "chart", data


@frappe.whitelist()
def get_form_charts(doctype=None, from_date=None, to_date=None):
    """
    Every question on one form, summarised for "easily interpreted at a
    glance" viewing - a pie/bar-ready count breakdown for categorical
    questions (Select/Check, or a Link field with few enough distinct
    answers), a plain answer list for free text. Works the same whether the
    form is anonymous or person-linked - this view was specifically asked
    for as the anonymous-forms answer, but is offered for every form since
    "just collect the data" is just as useful alongside person-by-person
    browsing on a linked form.
    """
    ensure_logged_in()

    meta = _form_doctype_meta(doctype)
    link_field = _form_link_field(meta)
    link_fieldname = link_field.fieldname if link_field else None

    filters = _form_date_range_filters(from_date, to_date)

    scope = _form_scope_filter_value(link_field)
    if scope is not None:
        filters[link_fieldname] = scope

    total_submissions = frappe.db.count(doctype, filters=filters)

    questions = []
    for df in _form_question_fields(meta):
        if df.fieldname == link_fieldname:
            continue

        kind, payload = _chart_bucket_for_field(df, doctype, filters)

        questions.append({
            "label": df.label or df.fieldname,
            "fieldtype": df.fieldtype,
            "kind": kind,
            "data": payload if kind == "chart" else None,
            "answers": payload if kind == "list" else None,
        })

    return {"total_submissions": total_submissions, "questions": questions}


@frappe.whitelist()
def get_form_module_doctypes():
    """
    Every DocType in the "Forms" module - powers the Reports section's
    form picker. Discovered from Frappe's own DocType metadata rather than
    a hardcoded list, so a form added in Desk shows up here with no code
    change needed.
    """
    ensure_logged_in()

    rows = frappe.get_all(
        "DocType",
        filters={"module": FORMS_MODULE, "istable": 0, "issingle": 0},
        fields=["name"],
        order_by="name asc",
    )

    rows = [row for row in rows if not _is_form_hidden(row.name)]

    if is_franchisor_user():
        rows = [row for row in rows if not _is_form_restricted_to_coaches(row.name)]
    else:
        rows = [row for row in rows if not _is_form_restricted_to_franchisors(row.name)]

    return [{"value": row.name, "label": row.name} for row in rows]


@frappe.whitelist()
def get_form_questions(doctype=None):
    """Every "question" (field) on one Forms-module doctype, for the "one question" view."""
    meta = _form_doctype_meta(doctype)
    link_field = _form_link_field(meta)
    link_fieldname = link_field.fieldname if link_field else None

    return [
        {"value": df.fieldname, "label": df.label or df.fieldname}
        for df in _form_question_fields(meta)
        if df.fieldname != link_fieldname
    ]


@frappe.whitelist()
def get_form_report(doctype=None, from_date=None, to_date=None):
    """Summary - every submission of one form, newest first."""
    ensure_logged_in()

    meta = _form_doctype_meta(doctype)
    link_field = _form_link_field(meta)

    filters = _form_date_range_filters(from_date, to_date)

    scope = _form_scope_filter_value(link_field)
    if scope is not None:
        filters[link_field.fieldname] = scope

    fields = ["name", "creation"]
    if link_field:
        fields.append(link_field.fieldname)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    link_doctype = link_field.options if link_field else None

    for row in rows:
        linked_name = row.get(link_field.fieldname) if link_field else None
        row["person_label"] = _form_person_label(link_doctype, linked_name)
        row["coach_label"] = _form_coach_label(link_doctype, linked_name)

    return {"rows": rows, "has_person_link": bool(link_field)}


@frappe.whitelist()
def get_form_answers_for_question(doctype=None, question=None, from_date=None, to_date=None):
    """Every submission's answer to one specific question."""
    ensure_logged_in()

    meta = _form_doctype_meta(doctype)
    link_field = _form_link_field(meta)

    question = (question or "").strip()
    matching = [df for df in _form_question_fields(meta) if df.fieldname == question]
    if not matching:
        frappe.throw(_("Unknown question."))
    df = matching[0]

    filters = _form_date_range_filters(from_date, to_date)

    scope = _form_scope_filter_value(link_field)
    if scope is not None:
        filters[link_field.fieldname] = scope

    fields = ["name", "creation", question]
    if link_field and link_field.fieldname != question:
        fields.append(link_field.fieldname)

    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by="creation desc",
        limit_page_length=2000,
        ignore_permissions=True,
    )

    link_doctype = link_field.options if link_field else None

    out = []
    for row in rows:
        linked_name = row.get(link_field.fieldname) if link_field else None
        out.append({
            "name": row.get("name"),
            "person_label": _form_person_label(link_doctype, linked_name),
            "coach_label": _form_coach_label(link_doctype, linked_name),
            "value": _form_field_value(row, df) or "",
        })

    return {"question": df.label or question, "rows": out}


@frappe.whitelist()
def get_form_submission(doctype=None, name=None):
    """
    Every answer on exactly one submission, by its own document name - the
    dashboard-side stand-in for opening the record in Frappe Desk, which
    coaches and franchisors don't have access to. Used by the "Link"
    column on the Form Results summary table.
    """
    ensure_logged_in()

    meta = _form_doctype_meta(doctype)
    link_field = _form_link_field(meta)

    name = (name or "").strip()
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(_("Submission not found."))

    linked_name = None
    if link_field:
        linked_name = frappe.db.get_value(doctype, name, link_field.fieldname)

        scope = _form_scope_filter_value(link_field)
        if scope is not None and linked_name not in (scope[1] or []):
            frappe.throw(_("You do not have permission to view this submission."), frappe.PermissionError)

    doc = frappe.get_doc(doctype, name)
    answers = [
        {"label": df.label or df.fieldname, "value": _form_field_value(doc, df)}
        for df in _form_question_fields(meta)
        if not link_field or df.fieldname != link_field.fieldname
    ]

    return {
        "name": doc.name,
        "submitted_on": doc.creation,
        "person": _form_person_label(link_field.options, linked_name) if link_field else "",
        "answers": [a for a in answers if a["value"] is not None],
    }


def _upsert_form_visibility_rule(doctype, visibility):
    if frappe.db.exists("Form Visibility Rule", doctype):
        frappe.db.set_value("Form Visibility Rule", doctype, "visibility", visibility)
    else:
        frappe.get_doc({
            "doctype": "Form Visibility Rule",
            "form_doctype": doctype,
            "visibility": visibility,
        }).insert(ignore_permissions=True)
    frappe.db.commit()


def sync_web_form_report_visibility(doc, method=None):
    """
    Web Form.on_update hook (see hooks.py) - lets "Show In Coach Reports"
    / "Show In Franchisor Reports" on the Web Form itself (see
    add_web_form_report_visibility_fields patch) drive the two things
    that actually control Reports-section visibility, without whoever
    built the form needing to know either exists:

    - get_form_module_doctypes() only discovers a DocType whose Module is
      "Forms" - ticking either box sets that here.
    - Form Visibility Rule's "visibility" then decides who, from the two
      boxes: both ticked -> "Everyone", coach only -> "Coaches Only",
      franchisor only -> "Franchisors Only".

    Unticking both sets the rule to "Hidden" rather than reverting the
    DocType's Module - a straight revert could fight whatever Module the
    DocType is meant to belong to for reasons unrelated to this app,
    whereas "Hidden" already fully suppresses it from the Form Results
    picker for everyone (see Form Visibility Rule's own field
    description) and is just as reversible by ticking a box again.
    """
    target = doc.get("doc_type")
    if not target or not frappe.db.exists("DocType", target):
        return

    meta_row = frappe.db.get_value("DocType", target, ["istable", "issingle"], as_dict=True)
    if not meta_row or meta_row.istable or meta_row.issingle:
        return

    show_coach = bool(doc.get("custom_show_in_coach_reports"))
    show_franchisor = bool(doc.get("custom_show_in_franchisor_reports"))

    if not show_coach and not show_franchisor:
        if frappe.db.exists("Form Visibility Rule", target):
            _upsert_form_visibility_rule(target, "Hidden")
        return

    if frappe.db.get_value("DocType", target, "module") != FORMS_MODULE:
        frappe.db.set_value("DocType", target, "module", FORMS_MODULE)
        frappe.clear_cache(doctype=target)

    if show_coach and show_franchisor:
        visibility = "Everyone"
    elif show_coach:
        visibility = "Coaches Only"
    else:
        visibility = "Franchisors Only"

    _upsert_form_visibility_rule(target, visibility)


def _client_display_name(client_name):
    if not client_name:
        return ""

    return (
        frappe.db.get_value("Client", client_name, "full_name")
        or client_name
    )


def _coach_label_for_client(client_name):
    if not client_name:
        return ""

    coach_name = frappe.db.get_value("Client", client_name, "primary_coach") or frappe.db.get_value(
        "Client", client_name, "attending_coach"
    )

    return get_coach_label(coach_name)
