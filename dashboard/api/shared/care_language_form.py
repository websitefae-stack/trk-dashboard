"""
Scoring for the "How I feel cared for at school" care languages quiz - a
custom (Desk-style) DocType created by
patches/create_care_languages_quiz_form.py, the same way every other
Reports-section form on this site is built. See that patch's own
docstring for why the scoring lives here (hooked via hooks.py's
doc_events) rather than as a file-based DocType controller - a custom=1
DocType doesn't have one.

Each of the 16 questions offers two statements, each tied to one of five
"care languages". The child picks whichever feels more true; whichever
language they picked most often is their top one. A tie is broken by
preferring the earlier language in LANGUAGE_LABELS' own order (Kind Words
first) - deterministic rather than arbitrary, and rare in practice with
16 questions to spread across only 5 languages.

get_care_language_pupils() below also lives here (rather than the
generic form_reports.py) since it's specific to this one form's own
grouping concept - every pupil's name next to their top language,
grouped by language, for actually sorting pupils into groups, rather
than just the aggregate percentage breakdown the generic chart view
(form_reports.get_form_charts) gives.
"""

import frappe

from dashboard.api.shared.permissions import ensure_logged_in
from dashboard.api.shared.form_reports import _form_date_range_filters

DOCTYPE = "Care Language Response"

LANGUAGE_LABELS = {
    "A": "Kind Words",
    "B": "Time Together",
    "C": "Helping Hands",
    "D": "Little Surprises",
    "E": "High Fives",
}

# (question number, [(option text, language letter), (option text, language letter)])
QUESTIONS = [
    (1, [
        ("When my teacher tells me I did something well", "A"),
        ("When my teacher spends a few minutes just with me", "B"),
    ]),
    (2, [
        ("When my teacher helps me sort out a problem", "C"),
        ("When my teacher gives me a sticker or small prize", "D"),
    ]),
    (3, [
        ("When my teacher writes a happy note on my work", "A"),
        ("When my teacher gives me a high five or fist bump", "E"),
    ]),
    (4, [
        ("When my teacher sits with me at lunch or break", "B"),
        ("When my teacher shows me exactly how to do something tricky", "C"),
    ]),
    (5, [
        ("When my teacher lets me choose a job or a treat", "D"),
        ("When my teacher gives me a thumbs up as I walk past", "E"),
    ]),
    (6, [
        ("When my teacher tells the class something good I did", "A"),
        ("When my teacher picks a small gift or badge for me", "D"),
    ]),
    (7, [
        ("When my teacher asks me about my day", "B"),
        ("When my teacher claps or cheers for me", "E"),
    ]),
    (8, [
        ("When my teacher says exactly what they're proud of me for", "A"),
        ("When my teacher checks my work is going okay", "C"),
    ]),
    (9, [
        ("When my teacher listens properly when I'm talking to them", "B"),
        ("When my teacher lets me pick something special to do", "D"),
    ]),
    (10, [
        ("When my teacher helps me get ready for something hard", "C"),
        ("When my teacher gives me a pat on the shoulder for good work", "E"),
    ]),
    (11, [
        ("When my teacher tells me they believe in me", "A"),
        ("When my teacher remembers something I told them before", "B"),
    ]),
    (12, [
        ("When my teacher explains something again without getting annoyed", "C"),
        ("When my teacher gives me a certificate or award", "D"),
    ]),
    (13, [
        ("When my teacher notices when I try hard, not just when I get it right", "A"),
        ("When my teacher does our secret handshake or special greeting", "E"),
    ]),
    (14, [
        ("When my teacher plays or does an activity with me", "B"),
        ("When my teacher helps me fix a mistake calmly", "C"),
    ]),
    (15, [
        ("When my teacher saves me something like a good pencil or seat", "D"),
        ("When my teacher gives me a big smile and a wave", "E"),
    ]),
    (16, [
        ("When my teacher says thank you for something I did", "A"),
        ("When my teacher sorts out a problem with a friend for me", "C"),
    ]),
]

_FIELD_BY_LETTER = {
    "A": "kind_words_score",
    "B": "time_together_score",
    "C": "helping_hands_score",
    "D": "little_surprises_score",
    "E": "high_fives_score",
}


def compute_care_language_score(doc, method=None):
    counts = {letter: 0 for letter in LANGUAGE_LABELS}

    for number, options in QUESTIONS:
        selected = (doc.get(f"q{number}") or "").strip()
        for text, letter in options:
            if text == selected:
                counts[letter] += 1
                break

    for letter, fieldname in _FIELD_BY_LETTER.items():
        doc.set(fieldname, counts[letter])

    top_letter = max(LANGUAGE_LABELS.keys(), key=lambda letter: counts[letter])
    doc.top_care_language = LANGUAGE_LABELS[top_letter]


@frappe.whitelist()
def get_care_language_pupils(from_date=None, to_date=None):
    """
    Every response's pupil name + year group, grouped by top_care_
    language (Kind Words/Time Together/Helping Hands/Little Surprises/
    High Fives, in that fixed order) - one row per response, same as
    the generic Summary view's own per-submission listing, since this
    form captures a free-text name with no link back to a Client and so
    has no reliable way to dedupe one child who's done the quiz twice
    under slightly different spellings.
    """
    ensure_logged_in()

    if not frappe.db.exists("DocType", DOCTYPE):
        return []

    filters = _form_date_range_filters(from_date, to_date)

    rows = frappe.get_all(
        DOCTYPE,
        filters=filters,
        fields=["pupil_name", "year_group", "top_care_language"],
        order_by="pupil_name asc",
        limit_page_length=0,
        ignore_permissions=True,
    )

    groups = {label: [] for label in LANGUAGE_LABELS.values()}
    for row in rows:
        language = row.top_care_language or ""
        if language not in groups:
            continue
        groups[language].append({"pupil_name": row.pupil_name or "", "year_group": row.year_group or ""})

    return [
        {"language": language, "pupils": groups[language]}
        for language in LANGUAGE_LABELS.values()
    ]
