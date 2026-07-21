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


def _normalised_email(value):
    return (value or "").strip().lower()


def _get_email_account_row(coach=None):
    """
    The current user's own Email Account, matched against frappe.session.user
    and coach.coach_email (the two addresses a coach's Email Account is
    plausibly keyed to). Matched case-insensitively and trimmed of
    whitespace, rather than an exact SQL "=" - a stray leading/trailing
    space or a capitalised letter in either the Email Account's email_id or
    Coach.coach_email is invisible in Desk's UI but silently fails a strict
    equality filter, so this compares normalised strings in Python instead
    of relying on the database to do it byte-for-byte.

    Only ever looks up by frappe.session.user or the coach doc
    _get_current_coach() already confirmed belongs to that same session -
    never an account name/email from the caller.
    """
    coach_email = (coach.get("coach_email") or "").strip() if coach else ""
    wanted = {_normalised_email(addr) for addr in (frappe.session.user, coach_email) if addr}

    if not wanted:
        return None

    rows = frappe.get_all(
        EMAIL_ACCOUNT_DOCTYPE,
        fields=["name", "email_id", "auth_method", "connected_app", "connected_user"],
        limit_page_length=0,
        ignore_permissions=True,
    )

    for row in rows:
        if _normalised_email(row.get("email_id")) in wanted:
            return row

    return None


def _ensure_email_account_ready(email_account_row, coach=None):
    if not email_account_row:
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    if (email_account_row.auth_method or "") != "OAuth":
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    if not (email_account_row.connected_app or "").strip():
        frappe.throw(_(NOT_CONFIGURED_MESSAGE))

    # Whichever address _get_email_account_row() actually matched this
    # Email Account on - frappe.session.user (the common case) or the
    # coach's own coach_email (when a coach's Frappe login differs from
    # their Workspace/Coach.coach_email address, e.g. the Email Account
    # was set up keyed to coach_email before this login existed).
    coach_email = (coach.get("coach_email") or "").strip() if coach else ""
    own_addresses = {_normalised_email(addr) for addr in (frappe.session.user, coach_email) if addr}

    connected_user = (email_account_row.connected_user or "").strip()

    if connected_user and _normalised_email(connected_user) not in own_addresses:
        # This Email Account is wired to someone else's mailbox - never let
        # one coach's click reassign it or start an OAuth flow against it.
        frappe.throw(_(NOT_CONFIGURED_MESSAGE), frappe.PermissionError)

    if not connected_user:
        # First-time setup for this coach's own account - safe to fill in,
        # since _get_email_account_row() already matched this row to one
        # of this session's own addresses above. The OAuth token itself is
        # always cached under frappe.session.user (initiate_web_application_flow
        # and has_token() both key off it below), so that's what gets
        # stored here regardless of which address found the row.
        frappe.db.set_value(
            EMAIL_ACCOUNT_DOCTYPE, email_account_row.name, "connected_user", frappe.session.user
        )
        frappe.db.commit()


def _not_configured_diagnostic_message(coach):
    """
    A more useful "not configured" message for the profile page specifically
    (never used in a frappe.throw(), so it's fine for it to name the address
    it searched for) - shows exactly which address(es) _get_email_account_row()
    tried and came up empty on, so a mismatch is visible from a screenshot
    alone instead of needing us to query the live database to diagnose it.
    """
    coach_email = (coach.get("coach_email") or "").strip() if coach else ""
    searched = frappe.session.user

    if coach_email and coach_email != frappe.session.user:
        searched = f"{frappe.session.user} or {coach_email}"

    return _(
        "No email account found for {0}. Ask the office to check that the Email Account "
        "record's email address matches one of those exactly."
    ).format(searched)


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
    coach = _get_current_coach()

    email_account_row = _get_email_account_row(coach)
    _ensure_email_account_ready(email_account_row, coach)

    success_path = _safe_return_to(return_to)
    separator = "&" if "?" in success_path else "?"
    success_uri = frappe.utils.get_url(success_path) + separator + "google_mail=connected"

    # The Email Account's own Connected App link, not a hardcoded name - a
    # Link field's stored value is the linked doc's docname, which is not
    # guaranteed to be the human-readable "Google Mail" label shown in
    # Desk's dropdown (that's just whichever field the Connected App
    # doctype uses as its title). Trusting the value office already picked
    # on this record is both correct and lets a different coach be wired to
    # a different Connected App without this code needing to change.
    try:
        connected_app = frappe.get_doc("Connected App", email_account_row.connected_app)
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
    coach = _get_current_coach()

    email_account_row = _get_email_account_row(coach)

    if (
        not email_account_row
        or (email_account_row.auth_method or "") != "OAuth"
        or not (email_account_row.connected_app or "").strip()
    ):
        return {
            "configured": False,
            "connected": False,
            "email": "",
            "message": _not_configured_diagnostic_message(coach),
        }

    # Frappe core's own has_token() - a whitelisted function we call
    # directly in Python (not over HTTP), so this still never touches the
    # Desk permission layer. Returns a plain bool; it never returns the
    # token itself. Keyed off this Email Account's own Connected App link
    # (see start_google_mail_connect()'s comment) rather than a hardcoded
    # name, so status stays in sync with whichever app the token was
    # actually issued against.
    from frappe.integrations.doctype.connected_app.connected_app import has_token

    connected = bool(has_token(email_account_row.connected_app, frappe.session.user))

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
