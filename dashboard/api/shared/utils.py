"""
Shared low-level helpers used across multiple API modules.
Keep this file free of Frappe model imports so it stays importable
at any point in the startup sequence.
"""


def get_label(row, fields):
    """
    Return the first non-empty value found on `row` for any key in `fields`.
    Falls back to row["name"] if nothing else matches.
    Used to produce human-readable labels from Frappe document dicts.
    """
    if not row:
        return ""

    for fieldname in fields:
        value = (row.get(fieldname) or "").strip()
        if value:
            return value

    return row.get("name") or ""
