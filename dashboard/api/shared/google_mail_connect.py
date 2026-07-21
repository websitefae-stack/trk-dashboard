"""
Lets a coach connect their own Google Workspace mailbox for sending email
from the dashboard - built on Frappe's Connected App credentials and Token
Cache storage, but with our own authorization-start and callback instead of
Frappe core's frappe.integrations.doctype.connected_app.connected_app
(initiate_web_application_flow()/callback()).

Why not just call those directly, like this module used to: Connected
App.redirect_uri is computed once, in Desk, from frappe.utils.get_url() -
which resolves to this site's single configured Host Name, not whichever
domain the browser is actually on. This site is reachable on several
different custom domains (coaches only ever use their own dashboard
domain, never the *.frappe.cloud one Desk lives on), so that fixed
redirect_uri sends Google's callback to a domain the coach was never
logged into. Frappe core's callback() then resolves the Token Cache to
check by frappe.session.user *on that domain* - a different, wrong, or
absent session there throws "Invalid token state" every time, regardless
of retrying, incognito, etc. See start_google_mail_connect() and
google_mail_callback() below for the fix: a redirect_uri computed from the
actual incoming request's own host, and a callback that identifies the
flow by its one-time OAuth `state` value (cached server-side at
authorization time) instead of by session identity.

Coaches never get Desk access or Email Account/Connected App doctype
permissions: every function below is a plain trusted server-side Python
call into those doctypes (frappe.get_doc / frappe.db.get_value), which
does not go through the doctype-permission-checked Desk RPC layer at all -
that's what lets a coach who has no read permission on "Connected App"
still trigger this flow for their own account. start_google_mail_connect()
and get_google_mail_status() act only on frappe.session.user; nothing
there accepts a user or email from the browser. google_mail_callback() is
necessarily guest-accessible (Google's redirect back may not carry a
recognised session - that's the whole problem being worked around) but
only ever acts on the user recorded server-side against the one-time
`state` value it's handed, never on anything else the request supplies.
"""

import frappe
from frappe import _

from dashboard.api.shared.profile import get_profile_doc

EMAIL_ACCOUNT_DOCTYPE = "Email Account"

NOT_CONFIGURED_MESSAGE = "Your email account has not yet been configured. Please contact the office."

CALLBACK_METHOD = "dashboard.api.shared.google_mail_connect.google_mail_callback"

# Keyed by the OAuth `state` value (a large, single-use, unguessable token
# minted by requests_oauthlib) - never by anything the browser could choose,
# so a 10 minute TTL is just cleanup, not a security boundary. Deleted the
# moment it's read in google_mail_callback() so it can't be replayed.
OAUTH_STATE_CACHE_PREFIX = "google_mail_oauth_state:"
OAUTH_STATE_TTL_SECONDS = 600


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
        # always cached under frappe.session.user (start_google_mail_connect(),
        # google_mail_callback() and has_token() all key off it), so that's
        # what gets stored here regardless of which address found the row.
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


def _request_origin():
    """
    scheme://host for the CURRENT request, e.g. "https://theresilienthub.co.uk" -
    deliberately not frappe.utils.get_url(), which ignores the request
    entirely and returns this site's one configured Host Name. Werkzeug's
    Request.host already reflects whichever of this site's several custom
    domains the browser actually used (Frappe's own multi-domain site
    routing depends on that being accurate), so this is the one reliable
    way to get a redirect_uri Google will send the coach's browser back to
    on the same domain they're logged into.
    """
    request = getattr(frappe.local, "request", None)
    if request is None or not request.host:
        return frappe.utils.get_url()
    scheme = "https" if request.is_secure else "http"
    return f"{scheme}://{request.host}"


def _oauth_state_cache_key(state):
    return OAUTH_STATE_CACHE_PREFIX + state


@frappe.whitelist()
def start_google_mail_connect(return_to=None):
    """
    Starts a Google OAuth authorization request for the CURRENT session
    user only, and redirects the browser to Google. See module docstring
    for why this doesn't just call Connected App's own
    initiate_web_application_flow().

    Meant to be hit by a direct browser navigation (a plain <a href> or
    window.location.href), not an AJAX call - frappe.local.response's
    "redirect" type only does anything useful when the browser itself
    follows it.
    """
    coach = _get_current_coach()

    email_account_row = _get_email_account_row(coach)
    _ensure_email_account_ready(email_account_row, coach)

    origin = _request_origin()

    success_path = _safe_return_to(return_to)
    separator = "&" if "?" in success_path else "?"
    success_uri = origin + success_path + separator + "google_mail=connected"

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

    # Point Google's redirect at OUR callback below, on THIS request's own
    # domain - not Connected App's own stored redirect_uri, which is fixed
    # to this site's single canonical Host Name (see module docstring).
    # This exact URL must be added to the OAuth Client's "Authorized
    # redirect URIs" in Google Cloud Console for every domain coaches
    # actually use the dashboard on.
    connected_app.redirect_uri = origin + "/api/method/" + CALLBACK_METHOD

    oauth = connected_app.get_oauth2_session(frappe.session.user, init=True)
    query_params = connected_app.get_query_params()
    authorization_url, state = oauth.authorization_url(connected_app.authorization_uri, **query_params)

    # Everything google_mail_callback() will need once Google redirects
    # back - looked up by `state` alone (see module docstring for why not
    # by session), and single-use: deleted the moment it's read.
    frappe.cache().set_value(
        _oauth_state_cache_key(state),
        {
            "user": frappe.session.user,
            "connected_app": connected_app.name,
            "redirect_uri": connected_app.redirect_uri,
            "success_uri": success_uri,
        },
        expires_in_sec=OAUTH_STATE_TTL_SECONDS,
    )

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = authorization_url


@frappe.whitelist(allow_guest=True, methods=["GET"])
def google_mail_callback(code=None, state=None):
    """
    Our own replacement for Connected App's stock callback() (see module
    docstring for why). Google redirects the coach's browser straight here
    with `code` and `state` - identifies which coach and which Connected
    App this belongs to purely from what start_google_mail_connect() cached
    against that `state` value a moment ago, never from frappe.session.user
    (which the whole point of this rewrite is to not depend on) and never
    from anything else in the request.
    """
    fallback = "/coach_db/profile?google_mail=failed"

    if not code or not state:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = fallback
        return

    cache_key = _oauth_state_cache_key(state)
    payload = frappe.cache().get_value(cache_key)
    frappe.cache().delete_value(cache_key)

    if not payload:
        # Expired (>10 minutes), already used, or a `state` nobody
        # recognises - never anything to act on.
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = fallback
        return

    user = payload.get("user")
    success_uri = payload.get("success_uri") or fallback

    try:
        connected_app = frappe.get_doc("Connected App", payload.get("connected_app"))
    except frappe.DoesNotExistError:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = fallback
        return

    # Must match exactly what was sent in the authorization request above,
    # per the OAuth spec - not recomputed from this (possibly different)
    # request, and not Connected App's own stored one either.
    connected_app.redirect_uri = payload.get("redirect_uri")

    oauth = connected_app.get_oauth2_session(user, init=True)
    query_params = connected_app.get_query_params()

    try:
        token = oauth.fetch_token(
            connected_app.token_uri,
            code=code,
            client_secret=connected_app.get_password("client_secret"),
            include_client_id=True,
            **query_params,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Google Mail Connect Failed")
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = fallback
        return

    token_cache = connected_app.get_token_cache(user) or frappe.new_doc("Token Cache")
    token_cache.user = user
    token_cache.connected_app = connected_app.name
    # update_data() sets the token fields, saves and commits - the exact
    # same Token Cache storage has_token() (used by get_google_mail_status()
    # below) already reads from, untouched.
    token_cache.update_data(token)

    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = success_uri


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
