"""
Scoring for the Stirling Children's Wellbeing Scale (SCWBS) - a standard,
published 15-item wellbeing self-report. The DocType/Web Form themselves
are created by a one-off patch (see
patches/create_stirling_wellbeing_scale_form.py) as a custom (Desk-style)
DocType, the same way every other Reports-section "form" on this site is
built - so this hooks in via hooks.py's doc_events (see the "Stirling
Wellbeing Response" entry) rather than a file-based DocType controller,
which a custom=1 DocType doesn't have.

Scoring key (Appendix D of the published scale):
- Wellbeing score: items 1, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14, 15 (12 items,
  1-5 each) summed - range 12-60.
- Social Desirability sub-scale: items 2, 7, 13 (3 items, 1-5 each) summed
  - range 3-15. A total of 3, or 14/15, means the wellbeing score should be
  treated with caution (the respondent may be answering how they think
  they're supposed to, not how they actually feel).

Also holds the Before/After comparison report (get_stirling_wellbeing_
comparison) - see patches/add_stirling_wellbeing_matching_fields.py for
why this form now collects Student First/Last Name and a School link
(it didn't originally - this was built fully anonymous), and the
Student Resilience Survey's own comparison report
(student_resilience_survey.py) for the identical pattern this follows:
the anonymisation happens here, server-side, never in the dashboard UI
- the response this sends back never includes a name field, only a
stable per-school "Student N" label.

The School link itself points at Client (client_type "School") as of
patches/switch_survey_school_fields_to_client.py - it originally
pointed at the sales-pipeline "School" doctype, which named its
records with a plain autoincrement number and showed up as a bare
number on the form.
"""

import frappe

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.patches.create_stirling_wellbeing_scale_form import DOCTYPE_NAME, STATEMENTS

# "school" is a Link to Client (client_type "School") - see
# switch_survey_school_fields_to_client.py.
SCHOOL_DOCTYPE = "Client"

WELLBEING_ITEM_NUMBERS = (1, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14, 15)
SOCIAL_DESIRABILITY_ITEM_NUMBERS = (2, 7, 13)


def _item_value(doc, item_number):
    # Each answer is stored as the full option text ("3 - Some of the
    # time"), not a bare number - a dropdown showing just "1, 2, 3, 4, 5"
    # with no indication what any of them mean would be useless to a kid
    # filling this in on their own, and the printed scale's column-header
    # legend has no equivalent on a single Select field. The score only
    # needs the leading digit back out of that text.
    raw = str(doc.get(f"q{item_number}") or "").strip()
    try:
        return int(raw.split(" ", 1)[0])
    except (TypeError, ValueError):
        return 0


def compute_stirling_wellbeing_score(doc, method=None):
    doc.wellbeing_score = sum(_item_value(doc, n) for n in WELLBEING_ITEM_NUMBERS)

    sd_score = sum(_item_value(doc, n) for n in SOCIAL_DESIRABILITY_ITEM_NUMBERS)
    doc.social_desirability_score = sd_score
    doc.validity_caution = 1 if sd_score in (3, 14, 15) else 0


_STAGES = ("Before", "After")


def _school_label(school_name):
    # A response saved before switch_survey_school_fields_to_client.py ran
    # still has the old School-pipeline-doctype value, which won't resolve
    # here - falls back to showing it raw rather than hiding it.
    if not school_name:
        return "Unknown School"

    if frappe.db.exists("DocType", SCHOOL_DOCTYPE):
        label = frappe.db.get_value(SCHOOL_DOCTYPE, school_name, "full_name")
        if label:
            return label

    return school_name


@frappe.whitelist()
def get_stirling_wellbeing_schools():
    """Every school with at least one Stirling response - powers the
    comparison report's School filter. No name data here at all."""
    ensure_logged_in()

    if not frappe.db.exists("DocType", DOCTYPE_NAME) or not frappe.get_meta(DOCTYPE_NAME).has_field("school"):
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
def get_stirling_wellbeing_comparison(school=None):
    """
    Every matched Before/After pair, grouped by school, with no name or
    other identifying field anywhere in the response - just a stable
    "Student N" label (numbered by earliest Before submission within
    that school). Mirrors student_resilience_survey.get_student_
    resilience_comparison - see that function's own docstring for the
    unmatched-pair and duplicate-submission handling, identical here.

    Responses from before this form collected a school/name at all
    (see add_stirling_wellbeing_matching_fields.py) have no school and
    no name, so they can never match anything - correctly excluded
    rather than guessed at.
    """
    ensure_logged_in()

    if not frappe.db.exists("DocType", DOCTYPE_NAME):
        return {"groups": [], "unmatched_count": 0}

    meta = frappe.get_meta(DOCTYPE_NAME)
    if not meta.has_field("student_first_name"):
        return {"groups": [], "unmatched_count": 0}

    item_fieldnames = [f"q{number}" for number, _statement in STATEMENTS]

    filters = {}
    school = (school or "").strip()
    if school:
        filters["school"] = school

    fields = ["name", "creation", "school", "student_first_name", "student_last_name", "survey_stage"]
    fields += item_fieldnames

    rows = frappe.get_all(
        DOCTYPE_NAME,
        filters=filters,
        fields=fields,
        order_by="creation asc",
        limit_page_length=20000,
        ignore_permissions=True,
    )

    matched_keys = {}
    for row in rows:
        key = (
            row.get("school"),
            (row.get("student_first_name") or "").strip().lower(),
            (row.get("student_last_name") or "").strip().lower(),
        )
        stage = row.get("survey_stage")
        if not key[0] or not key[1] or not key[2] or stage not in _STAGES:
            continue

        matched_keys.setdefault(key, {"Before": [], "After": []})
        matched_keys[key][stage].append(row)

    by_school = {}
    unmatched_count = 0

    for (school_name, _first, _last), stages in matched_keys.items():
        befores = stages["Before"]
        afters = stages["After"]

        if befores and afters:
            by_school.setdefault(school_name, []).append({"before": befores[-1], "after": afters[-1]})
        else:
            unmatched_count += len(befores) + len(afters)

    groups = []
    for school_name in sorted(by_school.keys(), key=_school_label):
        pairs = sorted(by_school[school_name], key=lambda p: p["before"]["creation"])

        pairs_out = []
        for index, pair in enumerate(pairs, start=1):
            before, after = pair["before"], pair["after"]

            before_items = {n: _item_value(before, n) for n in range(1, len(STATEMENTS) + 1)}
            after_items = {n: _item_value(after, n) for n in range(1, len(STATEMENTS) + 1)}

            before_wellbeing = sum(before_items[n] for n in WELLBEING_ITEM_NUMBERS)
            after_wellbeing = sum(after_items[n] for n in WELLBEING_ITEM_NUMBERS)
            before_sd = sum(before_items[n] for n in SOCIAL_DESIRABILITY_ITEM_NUMBERS)
            after_sd = sum(after_items[n] for n in SOCIAL_DESIRABILITY_ITEM_NUMBERS)

            questions = [
                {
                    "number": number,
                    "statement": statement,
                    "before": before_items.get(number),
                    "after": after_items.get(number),
                }
                for number, statement in STATEMENTS
            ]

            pairs_out.append({
                "label": f"Student {index}",
                "before_date": frappe.utils.formatdate(before.get("creation"), "dd-MM-yyyy"),
                "after_date": frappe.utils.formatdate(after.get("creation"), "dd-MM-yyyy"),
                "before_wellbeing_score": before_wellbeing,
                "after_wellbeing_score": after_wellbeing,
                "before_social_desirability_score": before_sd,
                "after_social_desirability_score": after_sd,
                "before_validity_caution": before_sd in (3, 14, 15),
                "after_validity_caution": after_sd in (3, 14, 15),
                "questions": questions,
            })

        groups.append({
            "school": school_name,
            "school_label": _school_label(school_name),
            "pairs": pairs_out,
        })

    return {"groups": groups, "unmatched_count": unmatched_count}
