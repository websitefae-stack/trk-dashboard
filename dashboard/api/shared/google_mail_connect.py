"""
Lets a coach connect their own Google Workspace mailbox for sending email
from the dashboard, reusing Frappe's existing Connected App / Email
Account / Token Cache OAuth machinery - not a custom OAuth implementation.

Coaches never get Desk access or Email Account/Connected App doctype
permissions: every function below is a plain trusted server-side Python
call into those doctypes (frappe.get_doc / frappe.db.get_value), which
does not go through the doctype-permission-checked Desk RPC layer at all -
that's what lets a coach who has no read permission on "Connected App"
still trigger this flow for their own account. Every function below also
acts ONLY on frappe.session.user; nothing here accepts a user or email
from the browser.
"""

import frappe
from frappe import _

from dashboard.api.shared.profile import get_profile_doc

CONNECTED_APP_NAME = "Google Mail"
EMAIL_ACCOUNT_DOCTYPE = "Email Account"

NOT_CONFIGURED_MESSAGE = "Your email account has not yet been configured. Please contact the office."


def _get_current_coach():
    """
    The Coach linked to frappe.session.user. get_profile_doc() (see
    profile.py) only ever matches Coach.user or Coach.coach_email against
    the CURRENT session user, so there is no path here that can resolve to
    anyone else's Coach record.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    coach = get_profile_doc("coach")

    if frappe.session.user not in (coach.get("user") or "", coach.get("coach_email") or ""):
        # get_profile_doc() already guarantees this by construction - kept
        # as an explicit hard stop rather than trusting that invariant
        # blindly, since it gates who an OAuth flow is allowed to run as.
        frappe.throw(_("Your account is not linked to a coach profile."), frappe.PermissionError)

    return coach


def _get_email_account_row():
    """
    The current user's own Email Account, matched by email_id ==
    frappe.session.user (a coach's Workspace address, their Frappe User
    email, and their Email Account's email_id are all the same address in
    this setup). Never accepts an account name/email from the caller.
    """
    return frappe.db.get_value(
        EMAIL_ACCOUNT_DOCTYPE,
        {"email_id": frappe.session.user},
        ["name", "email_id", "auth_method", "connected_app", "connected_user"],
        as_dict=True,
    )


def _ensure_email_account_ready(email_account_row):
    if not email_account_row:
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    if (email_account_row.auth_method or "") != "OAuth":
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    if (email_account_row.connected_app or "") != CONNECTED_APP_NAME:
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    connected_user = (email_account_row.connected_user or "").strip()

    if connected_user and connected_user != frappe.session.user:
        # This Email Account is wired to someone else's mailbox - never let
        # one coach's click reassign it or start an OAuth flow against it.
        frappe.throw(_(NOT_CONFIGURED_MESSAGE), frappe.PermissionError)

    if not connected_user:
        # First-time setup for this coach's own account - safe to fill in,
        # since email_id already matched frappe.session.user above.
        frappe.db.set_value(
            EMAIL_ACCOUNT_DOCTYPE, email_account_row.name, "connected_user", frappe.session.user
        )
        frappe.db.commit()


def _safe_return_to(return_to):
    return_to = (return_to or "").strip()
    if return_to.startswith("/coach_db/"):
        return return_to
    return "/coach_db/profile"


@frappe.whitelist()
def start_google_mail_connect(return_to=None):
    """
    Starts Frappe's standard Connected App OAuth flow (state, Token Cache,
    the works - see frappe.integrations.doctype.connected_app) for the
    CURRENT session user only, and redirects the browser to Google.

    Meant to be hit by a direct browser navigation (a plain <a href> or
    window.location.href), not an AJAX call - frappe.local.response's
    "redirect" type only does anything useful when the browser itself
    follows it.
    """
    _get_current_coach()

    email_account_row = _get_email_account_row()
    _ensure_email_account_ready(email_account_row)

    success_path = _safe_return_to(return_to)
    separator = "&" if "?" in success_path else "?"
    success_uri = frappe.utils.get_url(success_path) + separator + "google_mail=connected"

    try:
        connected_app = frappe.get_doc("Connected App", CONNECTED_APP_NAME)
    except frappe.DoesNotExistError:
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    # initiate_web_application_flow() builds the Google authorization URL,
    # generates the OAuth state, and saves it on this user's Token Cache
    # row (creating it if needed) - all standard Frappe Connected App
    # behaviour, untouched. It always resolves the token cache under
    # "<connected_app>-<user>", so passing frappe.session.user explicitly
    # here is what pins the whole flow to the coach who clicked the button
    # and nobody else.
    authorization_url = connected_app.initiate_web_application_flow(
        user=frappe.session.user,
        success_uri=success_uri,
    )

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = authorization_url


@frappe.whitelist()
def get_google_mail_status():
    """
    Status for the dashboard's "Connect Google Email" section. Reports
    only on frappe.session.user's own account - never a token, secret, or
    another user's connection state.
    """
    _get_current_coach()

    email_account_row = _get_email_account_row()

    if (
        not email_account_row
        or (email_account_row.auth_method or "") != "OAuth"
        or (email_account_row.connected_app or "") != CONNECTED_APP_NAME
    ):
        return {
            "configured": False,
            "connected": False,
            "email": "",
            "message": NOT_CONFIGURED_MESSAGE,
        }

    # Frappe core's own has_token() - a whitelisted function we call
    # directly in Python (not over HTTP), so this still never touches the
    # Desk permission layer. Returns a plain bool; it never returns the
    # token itself.
    from frappe.integrations.doctype.connected_app.connected_app import has_token

    connected = bool(has_token(CONNECTED_APP_NAME, frappe.session.user))

    return {
        "configured": True,
        "connected": connected,
        "email": email_account_row.email_id or "",
        "message": (
            "Google Email Connected."
            if connected
            else "Connect Google Email to enable sending from your own account."
        ),
    }
