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
"""

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
