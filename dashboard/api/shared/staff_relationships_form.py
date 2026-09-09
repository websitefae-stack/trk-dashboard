"""
Scoring for the "Relationships with staff" questionnaire (Wellbeing
Measurement for Schools, Anna Freud / CORC) - see
school_experience_form.py's own module docstring for why this lives here
rather than a file-based DocType controller (a custom=1 DocType, created
by patches/create_staff_relationships_form.py, doesn't have one).

4 statements ("At school, there is an adult who...") each scored 1-5
(Never...Always). Total score (4-20) indicates the pupil's perception of
their relationships with school staff - higher is better.
"""

QUESTION_NUMBERS = (1, 2, 3, 4)


def _item_value(doc, item_number):
    raw = str(doc.get(f"q{item_number}") or "").strip()
    try:
        return int(raw.split(" ", 1)[0])
    except (TypeError, ValueError):
        return 0


def compute_staff_relationships_score(doc, method=None):
    doc.total_score = sum(_item_value(doc, number) for number in QUESTION_NUMBERS)
