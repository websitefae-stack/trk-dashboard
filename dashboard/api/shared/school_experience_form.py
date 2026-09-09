"""
Scoring for the "School experience" questionnaire (Wellbeing Measurement
for Schools, Anna Freud / CORC) - a custom (Desk-style) DocType created by
patches/create_school_experience_form.py, the same way every other
Reports-section form on this site is built. See that patch's own
docstring for why the scoring lives here (hooked via hooks.py's
doc_events) rather than as a file-based DocType controller - a custom=1
DocType doesn't have one.

4 statements, each scored 0-3 (Never/A little bit/A lot/Always). Total
score (0-12) indicates the pupil's overall experience of school - higher
is better.
"""

QUESTION_NUMBERS = (1, 2, 3, 4)


def _item_value(doc, item_number):
    # Stored as the full option text ("2 - A lot"), not a bare number -
    # same reasoning as the Stirling scale's own scoring (see
    # wellbeing_forms.py): a dropdown showing just "0, 1, 2, 3" with no
    # indication what any of them mean would be useless to a kid filling
    # this in on their own.
    raw = str(doc.get(f"q{item_number}") or "").strip()
    try:
        return int(raw.split(" ", 1)[0])
    except (TypeError, ValueError):
        return 0


def compute_school_experience_score(doc, method=None):
    doc.total_score = sum(_item_value(doc, number) for number in QUESTION_NUMBERS)
