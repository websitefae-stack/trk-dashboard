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
"""

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
