"""
Before/After comparison for the Student Resilience Survey (see
patches/create_student_resilience_survey_form.py for the DocType and
its 40-question SECTIONS structure, reused here so the question list
only ever lives in one place).

The underlying DocType holds First/Last Name as the matching key (see
that patch's own docstring for why - Ashley's choice over a self-
generated anonymous code), which makes it identifiable data, not
anonymous - so its own DocType permission is System Manager only, and
it's deliberately kept OUT of the generic Forms-module report
(form_reports.py) that every other public form shows up in.

What coaches and the franchisor actually asked for is a comparison
tool that shows the before/after answers without any identifying
information at all - so this reads the raw data with
ignore_permissions=True (same pattern form_reports.py's own report
functions already use for forms with restricted DocType permissions)
but the response this sends back never includes a name field anywhere,
only a stable per-school "Student N" label. The anonymisation happens
here, server-side - not just hidden in the dashboard UI - so it holds
even if someone inspects the raw API response.

No coach/school linkage exists anywhere else in this app (Client has a
coach field, School doesn't), so this is deliberately not scoped to
"only the coach who ran this school's programme" - any logged-in coach
or franchisor can see every school's comparison data, same gate as any
other un-scoped report in this module.
"""

import frappe
from frappe import _

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.patches.create_student_resilience_survey_form import DOCTYPE_NAME, SCHOOL_DOCTYPE, SECTIONS

_STAGES = ("Before", "After")


def _school_label(school_name):
    if not school_name:
        return "Unknown School"

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        label = frappe.db.get_value(SCHOOL_DOCTYPE, school_name, "school_name")
        if label:
            return label

    return school_name


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _average(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


@frappe.whitelist()
def get_student_resilience_schools():
    """Every school with at least one survey response - powers the
    comparison report's School filter. No name data here at all."""
    ensure_logged_in()

    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return []

    school_names = frappe.get_all(
        DOCTYPE_NAME,
        filters={"school": ["is", "set"]},
        pluck="school",
        distinct=True,
        ignore_permissions=True,
    )

    rows = [{"value": name, "label": _school_label(name)} for name in school_names]
    return sorted(rows, key=lambda r: r["label"])


@frappe.whitelist()
def get_student_resilience_comparison(school=None):
    """
    Every matched Before/After pair, grouped by school, with no name or
    other identifying field anywhere in the response - just a stable
    "Student N" label (numbered by earliest Before submission within
    that school, so the same pair is always "Student N" on a re-run).

    A student with only a Before (no After yet, or vice versa) isn't
    shown as a pair - counted in unmatched_count instead, so nothing
    silently goes missing without it being visible that it happened.
    If duplicate Before (or After) rows exist for the same matched
    student, the most recent one is used.
    """
    ensure_logged_in()

    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return {"groups": [], "unmatched_count": 0}

    question_fieldnames = [fieldname for _, _, questions in SECTIONS for fieldname, _ in questions]

    filters = {}
    school = (school or "").strip()
    if school:
        filters["school"] = school

    fields = ["name", "creation", "school", "student_first_name", "student_last_name", "survey_stage"]
    fields += question_fieldnames

    rows = frappe.get_all(
        DOCTYPE_NAME,
        filters=filters,
        fields=fields,
        order_by="creation asc",
        limit_page_length=20000,
        ignore_permissions=True,
    )

    # (school, normalised first name, normalised last name) -> {"Before": [...], "After": [...]}
    matched_keys = {}
    for row in rows:
        key = (
            row.get("school"),
            (row.get("student_first_name") or "").strip().lower(),
            (row.get("student_last_name") or "").strip().lower(),
        )
        stage = row.get("survey_stage")
        if stage not in _STAGES:
            continue

        matched_keys.setdefault(key, {"Before": [], "After": []})
        matched_keys[key][stage].append(row)

    by_school = {}
    unmatched_count = 0

    for (school_name, _first, _last), stages in matched_keys.items():
        befores = stages["Before"]
        afters = stages["After"]

        if befores and afters:
            by_school.setdefault(school_name, []).append({
                "before": befores[-1],
                "after": afters[-1],
            })
        else:
            unmatched_count += len(befores) + len(afters)

    groups = []
    for school_name in sorted(by_school.keys(), key=_school_label):
        pairs = sorted(by_school[school_name], key=lambda p: p["before"]["creation"])

        pairs_out = []
        for index, pair in enumerate(pairs, start=1):
            before, after = pair["before"], pair["after"]

            section_averages = []
            overall_before_values = []
            overall_after_values = []

            questions = []
            for _break_fieldname, section_label, section_questions in SECTIONS:
                before_values = []
                after_values = []

                for fieldname, statement in section_questions:
                    before_value = _safe_int(before.get(fieldname))
                    after_value = _safe_int(after.get(fieldname))

                    if before_value is not None:
                        before_values.append(before_value)
                        overall_before_values.append(before_value)
                    if after_value is not None:
                        after_values.append(after_value)
                        overall_after_values.append(after_value)

                    questions.append({
                        "section": section_label,
                        "question": statement,
                        "before": before_value,
                        "after": after_value,
                    })

                section_averages.append({
                    "section": section_label,
                    "before_avg": _average(before_values),
                    "after_avg": _average(after_values),
                })

            pairs_out.append({
                "label": f"Student {index}",
                "before_date": frappe.utils.formatdate(before.get("creation"), "dd-MM-yyyy"),
                "after_date": frappe.utils.formatdate(after.get("creation"), "dd-MM-yyyy"),
                "overall_before_avg": _average(overall_before_values),
                "overall_after_avg": _average(overall_after_values),
                "section_averages": section_averages,
                "questions": questions,
            })

        groups.append({
            "school": school_name,
            "school_label": _school_label(school_name),
            "pairs": pairs_out,
        })

    return {"groups": groups, "unmatched_count": unmatched_count}
