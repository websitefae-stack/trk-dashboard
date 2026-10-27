"""
One-off, read-only diagnostic - Sam Male's coach profile keeps showing
"No email account found for sam@theresilientkid.co.uk..." on the Google
Connection tab, even after a hard refresh (so it isn't page-cache
staleness). get_google_mail_status() in google_mail_connect.py collapses
three different failure modes into that one message text:
  1. no Email Account row matches Coach.user/coach_email at all,
  2. a row matches but its auth_method isn't "OAuth", or
  3. a row matches but its connected_app is blank.
_get_email_account_row() already compares case/whitespace-normalised, so
a stray space or capital letter wouldn't explain this - but a genuinely
different address (typo, wrong domain) or a mismatched auth_method/
connected_app would, and the message text alone can't tell us which.

Logs:
1. Sam's Coach record (name, user, coach_email, coach_name) - confirms
   exactly which two addresses _get_email_account_row() is searching for.
2. Every Email Account row (name, email_id, auth_method, connected_app,
   connected_user), so a mismatch is visible directly instead of guessed.
3. Whether Sam's addresses match any Email Account row under the same
   normalisation _get_email_account_row() uses, and if so why
   _ensure_email_account_ready()/get_google_mail_status() would still
   call it "not configured" (auth_method/connected_app check).

Safe to delete once the cause is found and the actual record fixed by
hand in Desk.
"""

import frappe


def _normalised(value):
    return (value or "").strip().lower()


def execute():
    if not frappe.db.exists("DocType", "Coach"):
        frappe.log_error("Coach doctype does not exist", "Diag: Sam Male Google mail status")
        return

    coach_rows = frappe.get_all(
        "Coach",
        filters=[
            ["coach_name", "like", "%Sam%"],
        ],
        fields=["name", "user", "coach_email", "coach_name"],
    )

    # Also catch coaches whose name doesn't contain "Sam" but whose login
    # or coach_email does (covers a mismatched coach_name on the record).
    email_match_rows = frappe.get_all(
        "Coach",
        filters=[["coach_email", "like", "%sam@theresilientkid%"]],
        fields=["name", "user", "coach_email", "coach_name"],
    )
    for row in email_match_rows:
        if row["name"] not in {r["name"] for r in coach_rows}:
            coach_rows.append(row)

    email_account_rows = frappe.get_all(
        "Email Account",
        fields=["name", "email_id", "auth_method", "connected_app", "connected_user"],
        limit_page_length=0,
    )

    lines = ["Coach record(s) matching 'Sam':"]
    for row in coach_rows:
        lines.append(f"  {row}")

        wanted = {_normalised(addr) for addr in (row.get("user"), row.get("coach_email")) if addr}
        lines.append(f"    normalised addresses searched: {wanted}")

        matches = [
            ea for ea in email_account_rows
            if _normalised(ea.get("email_id")) in wanted
        ]
        if not matches:
            lines.append("    -> NO Email Account row matches either address (even normalised).")
        for ea in matches:
            reasons = []
            if (ea.get("auth_method") or "") != "OAuth":
                reasons.append(f"auth_method is {ea.get('auth_method')!r}, not 'OAuth'")
            if not (ea.get("connected_app") or "").strip():
                reasons.append("connected_app is blank")
            status = "OK (would report configured)" if not reasons else "NOT READY: " + "; ".join(reasons)
            lines.append(f"    -> matched Email Account {ea.get('name')!r} ({ea}): {status}")

    lines.append("\nAll Email Account rows currently in the system:")
    for ea in email_account_rows:
        lines.append(f"  {ea}")

    frappe.log_error("\n".join(lines), "Diag: Sam Male Google mail status")
