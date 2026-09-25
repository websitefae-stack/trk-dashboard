"""
Frappe's own communication-thread notifier can queue an outgoing "copy
this reply to everyone else who was on the thread" email using the
ORIGINAL external sender's address (e.g. a client who replied to a
booking confirmation, with someone here in CC) as the envelope sender,
while actually relaying it out through one of our own connected mailboxes
(e.g. The Resilient Office). Any properly configured mail provider
(Microsoft 365 here) correctly rejects that outright - you can't send
mail claiming to be from an address you don't own - so this always
failed with "553 5.7.1 ... Sender address rejected: not owned by user
...". Nothing was ever actually lost when this happened - the original
reply is still saved as its own Communication, linked to whatever it
replied to - only this superfluous "let everyone else on the thread
know" copy kept bouncing and cluttering the Email Queue.

fix_spoofed_relay_sender rewrites the sender - both the envelope-level
Email Queue.sender field (what's actually passed to smtplib as MAIL
FROM, per email_queue.py's send()) and the message's own From: header,
for consistency - to the connected Email Account's own, actually-owned
address whenever the two differ. Every genuine outgoing email already
uses that same address as its sender, so this only ever touches the one
broken "relay a reply's original headers on to a CC'd party" case,
regardless of which Frappe feature queued it.
"""

import email

import frappe


def fix_spoofed_relay_sender(doc, method=None):
    if not doc.email_account or not doc.sender:
        return

    account_meta = frappe.get_meta("Email Account")
    account_fields = ["email_id"]
    if account_meta.has_field("sender_name"):
        account_fields.append("sender_name")

    account = frappe.db.get_value("Email Account", doc.email_account, account_fields, as_dict=True)
    account_email = account.get("email_id") if account else None

    if not account_email or doc.sender == account_email:
        return

    account_display_name = account.get("sender_name") if account else None
    from_header = f"{account_display_name} <{account_email}>" if account_display_name else account_email

    doc.sender = account_email

    if not doc.message:
        return

    try:
        parsed = email.message_from_string(doc.message)
    except Exception:
        return

    if parsed.get("From"):
        del parsed["From"]
        parsed["From"] = from_header
        doc.message = parsed.as_string()
