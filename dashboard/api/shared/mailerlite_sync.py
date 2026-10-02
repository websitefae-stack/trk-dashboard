"""
Two-way subscriber sync between Frappe's Email Groups (EVERY one -
newsletter subscribers, course sign-ups, website customers, etc, all
merged into the single MailerLite Group ID on MailerLite Settings) and
MailerLite, Ashley's actual newsletter sending tool - this app never
sends the newsletter itself (see the email strategy discussion this
came out of: MailerLite stays the system of record for the
900-subscriber weekly send, keeping bulk marketing mail off office@
entirely, which also protects office@'s own deliverability for
invoices/booking confirmations).

Deliberately ONE-DIRECTIONAL for new subscribers (Frappe -> MailerLite
only, never the reverse) - someone who signs up directly in MailerLite
was never asked to also become a Frappe contact, so pulling them in
here would create data nobody asked for. Unsubscribes flow BOTH ways
though, since either side is a genuine "stop emailing me" signal that
has to be honoured everywhere, immediately - see sync_unsubscribe_to_
mailerlite (Frappe -> MailerLite) and mailerlite_webhook (MailerLite ->
Frappe, which only ever marks EXISTING Frappe members unsubscribed -
in every Email Group they're in, since MailerLite only has one merged
list to unsubscribe them from - never creates a new one, same
one-directional rule for additions).

Built from MailerLite's documented API shape (connect.mailerlite.com) -
this sandbox has no outbound internet access to verify against their
live docs at build time, so treat the first real sync/webhook delivery
as the actual test: _mailerlite_request logs the exact status code and
response body on any error rather than failing silently, so a wrong
endpoint or field name is a quick one-line fix once it's visible in
Error Log, not a mystery.
"""

import hashlib
import hmac
import json

import frappe
import requests

from dashboard.api.shared.permissions import ensure_office_user

MAILERLITE_API_BASE = "https://connect.mailerlite.com/api"
SETTINGS_DOCTYPE = "MailerLite Settings"


def _get_settings():
    if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        return None
    return frappe.get_single(SETTINGS_DOCTYPE)


def _mailerlite_request(method, path, payload=None):
    settings = _get_settings()
    if not settings:
        return None

    api_key = settings.get_password("api_key", raise_exception=False)
    if not api_key:
        return None

    url = f"{MAILERLITE_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.request(method, url, headers=headers, json=payload, timeout=15)
    except requests.RequestException:
        frappe.log_error(frappe.get_traceback(), f"MailerLite API {method} {path} - request failed")
        return None

    if response.status_code >= 400:
        frappe.log_error(
            f"MailerLite API {method} {path} returned {response.status_code}: {response.text[:2000]}",
            "MailerLite API Error",
        )
        return None

    if not response.content:
        return {}

    try:
        return response.json()
    except ValueError:
        return {}


@frappe.whitelist()
def backfill_mailerlite_subscribers():
    """
    One-off, office-triggered sync of everyone ALREADY in a Frappe Email
    Group before MailerLite Settings was ever configured - sync_new_
    email_group_member only ever fires on a brand new Email Group Member
    row (Frappe's after_insert hook), so nobody who joined before this
    integration existed has ever been pushed. Visit this URL directly
    while logged in as office to run it:
    /api/method/dashboard.api.shared.mailerlite_sync.backfill_mailerlite_
    subscribers

    Runs in the background (several hundred people means several hundred
    API calls, too slow for one HTTP request) - check Error Log for
    "MailerLite Backfill Complete" once it's done. Safe to re-run any
    time: push_subscriber_to_mailerlite is an upsert on MailerLite's own
    side, so someone already there just gets updated, never duplicated.
    """
    ensure_office_user()
    frappe.enqueue(
        "dashboard.api.shared.mailerlite_sync._backfill_mailerlite_subscribers",
        queue="long",
    )
    return {"ok": 1, "message": "Backfill started in the background - check Error Log for a summary once it finishes."}


def _backfill_mailerlite_subscribers():
    settings = _get_settings()
    if not settings or not settings.group_id:
        return

    fields = ["email"]
    if frappe.get_meta("Email Group Member").has_field("full_name"):
        fields.append("full_name")

    members = frappe.get_all("Email Group Member", filters={"unsubscribed": 0}, fields=fields)

    seen = set()
    pushed = 0

    for member in members:
        email = (member.email or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        push_subscriber_to_mailerlite(email, member.get("full_name"))
        pushed += 1

    frappe.log_error(
        f"Backfilled {pushed} subscriber(s) to MailerLite out of {len(members)} Email Group Member row(s) checked.",
        "MailerLite Backfill Complete",
    )


def push_subscriber_to_mailerlite(email, full_name=None):
    settings = _get_settings()
    if not settings or not settings.group_id:
        return

    email = (email or "").strip().lower()
    if not email:
        return

    payload = {"email": email, "groups": [settings.group_id]}

    if full_name:
        payload["fields"] = {"name": full_name}

    _mailerlite_request("POST", "/subscribers", payload)


def unsubscribe_in_mailerlite(email):
    email = (email or "").strip().lower()
    if not email:
        return

    settings = _get_settings()
    if not settings:
        return

    # MailerLite's subscriber endpoints accept the email address directly
    # in place of the numeric subscriber ID.
    _mailerlite_request("PUT", f"/subscribers/{email}", {"status": "unsubscribed"})


def sync_new_email_group_member(doc, method=None):
    """Email Group Member.after_insert hook."""
    try:
        _sync_new_email_group_member(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"MailerLite Push Failed - {doc.name}")


def _sync_new_email_group_member(doc):
    settings = _get_settings()
    if not settings:
        return

    if doc.get("unsubscribed"):
        return

    full_name = doc.get("full_name") if doc.meta.has_field("full_name") else None
    push_subscriber_to_mailerlite(doc.email, full_name)


def sync_unsubscribe_to_mailerlite(doc, method=None):
    """Email Group Member.on_update hook - fires on every save, only
    acts the moment `unsubscribed` actually flips 0 -> 1."""
    try:
        _sync_unsubscribe_to_mailerlite(doc)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"MailerLite Unsubscribe Push Failed - {doc.name}")


def _sync_unsubscribe_to_mailerlite(doc):
    settings = _get_settings()
    if not settings:
        return

    if not doc.get("unsubscribed"):
        return

    previous = doc.get_doc_before_save()
    if previous and previous.get("unsubscribed"):
        # Already unsubscribed before this save - don't re-push to
        # MailerLite on every unrelated edit to this row.
        return

    unsubscribe_in_mailerlite(doc.email)


def _verify_webhook_signature(payload_bytes, signature_header, signing_secret):
    if not signing_secret or not signature_header:
        return False

    expected = hmac.new(signing_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def mailerlite_webhook():
    """
    MailerLite -> Frappe unsubscribe sync. Register this URL
    (https://theresilienthub.co.uk/api/method/dashboard.api.shared.
    mailerlite_sync.mailerlite_webhook) under MailerLite's own
    Integrations > Webhooks, subscribed to the "Subscriber
    unsubscribed" event only - new-subscriber events are deliberately
    never handled here (see this module's own docstring on why).

    Every delivery is logged once regardless of outcome (see the
    "MailerLite Webhook Received" entry in Error Log), specifically so
    the very first real one can be read back if the field names assumed
    below turn out to differ from what MailerLite actually sends.
    """
    settings = _get_settings()
    if not settings:
        frappe.local.response.http_status_code = 400
        return {"ok": False}

    signing_secret = settings.get_password("webhook_signing_secret", raise_exception=False)
    payload_bytes = frappe.request.get_data()
    signature = frappe.get_request_header("X-MailerLite-Signature")

    if signing_secret and not _verify_webhook_signature(payload_bytes, signature, signing_secret):
        frappe.log_error(
            "MailerLite webhook signature verification failed - check Webhook Signing Secret on "
            "MailerLite Settings matches what MailerLite's dashboard shows for this webhook.",
            "MailerLite Webhook Rejected",
        )
        frappe.local.response.http_status_code = 400
        return {"ok": False}

    try:
        body = json.loads(payload_bytes or b"{}")
    except ValueError:
        body = {}

    frappe.log_error(json.dumps(body)[:2000], "MailerLite Webhook Received")

    event_type = body.get("event") or body.get("type") or ""
    subscriber = body.get("data") or body.get("subscriber") or {}
    email = (subscriber.get("email") or "").strip().lower()

    if "unsubscrib" in str(event_type).lower() and email:
        _mark_unsubscribed_in_frappe(email)

    return {"ok": True}


def _mark_unsubscribed_in_frappe(email):
    settings = _get_settings()
    if not settings:
        return

    # Only ever updates EXISTING members - never creates one. Someone
    # who unsubscribes in MailerLite but was never known to Frappe has
    # nothing here to update, which is correct (see this module's own
    # docstring - additions only ever flow Frappe -> MailerLite).
    #
    # Updates every Email Group this email belongs to, not just one -
    # MailerLite only has the one merged list to unsubscribe them from,
    # so there's no way to know which single Frappe group they meant;
    # treating it as "stop emailing me everywhere" is the safer read of
    # an unsubscribe than under-honouring it in groups left unmatched.
    existing_names = frappe.get_all(
        "Email Group Member",
        filters={"email": email, "unsubscribed": 0},
        pluck="name",
    )

    if not existing_names:
        return

    for name in existing_names:
        frappe.db.set_value("Email Group Member", name, "unsubscribed", 1)

    frappe.db.commit()
