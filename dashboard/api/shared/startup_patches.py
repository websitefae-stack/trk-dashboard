"""
Defensive patches applied once when this app's module is imported (every
worker process, at boot) - never site-specific, so always safe to run
regardless of which site/context is importing the app.
"""

import frappe


def patch_get_modules_from_app_none_safety():
    """
    Frappe core's get_modules_from_all_apps() (frappe/utils/modules.py)
    does `modules_list += get_modules_from_app(app)` for every installed
    app on the bench. If even one other app's modules.txt is missing or
    empty and that returns None instead of [] - a bug in that other
    app, not any of this bench's own 4 (dashboard/client_portal/
    resilient_domains/coach_calendar_sync all have a normal, non-empty
    modules.txt, confirmed) - the whole thing throws
    TypeError: 'NoneType' object is not iterable.

    That crashes the stock Blog app's own has_permission hook
    (blog.check_app_permission calls get_modules_from_all_apps_for_user,
    which calls the function above) on every single request from an
    anonymous visitor - including a browser's own automatic favicon/
    apple-touch-icon probe, which never involves a real person at all.
    Logged to Error Log as "Failed to call has_permission hook
    (blog.check_app_permission) for blog" - confirmed harmless (Ashley
    asked for it not to show up unless it's an actual threat; it never
    is, since it only ever fires on this exact framework plumbing, never
    anything a real visitor's request depends on).

    Fixed here, not in Blog or whichever other app actually has the
    empty modules.txt (this bench doesn't control that app's source),
    by making get_modules_from_app defensively treat a None return as
    an empty list, so the permission check succeeds instead of crashing.
    Idempotent - safe if this ever runs more than once in the same
    process.
    """
    try:
        import frappe.utils.modules as modules_utils
    except Exception:
        return

    current = getattr(modules_utils, "get_modules_from_app", None)
    if current is None or getattr(current, "_dashboard_none_safe", False):
        return

    original_get_modules_from_app = current

    def _none_safe_get_modules_from_app(app):
        try:
            return original_get_modules_from_app(app) or []
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"get_modules_from_app failed for {app}",
            )
            return []

    _none_safe_get_modules_from_app._dashboard_none_safe = True
    modules_utils.get_modules_from_app = _none_safe_get_modules_from_app
