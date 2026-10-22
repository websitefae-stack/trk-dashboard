"""
Makes the "school" Select field on the Student Resilience Survey and
Children's Wellbeing Check-In always reflect the current School-type
Client list, rather than the one-time snapshot switch_survey_school_
fields_to_select.py baked into the field's options - Ashley wants this
to always, and only, pull client_type "School" clients, not need a
manual refresh when a new school signs up.

Sets each Web Form's client_script to plain, dependency-free
JavaScript (a polling loop + fetch, no Frappe-internal hook names)
that, once the school <select> element exists in the page, replaces
its options with a live call to school_client_options.
get_school_client_names (a narrow, guest-safe endpoint that returns
only school names - see that module's own docstring for why Client
itself can't be queried directly from a public, no-login form).

Written as plain JS rather than a frappe.web_form.on_load/after_load
hook deliberately - see switch_survey_school_fields_to_client.py and
fix_school_field_filter_script.py: the previous attempt at exactly
this kind of live behaviour used frappe.web_form.on_load, which
silently doesn't exist (the real hook is after_load), and never ran. A
plain top-level script doesn't depend on knowing the right Frappe hook
name at all - it just polls the DOM directly - so this isn't betting
on an undocumented internal API being right a second time.

The field's baked-in options (from the previous patch) are left as
they are and still used as a fallback for the brief moment before this
script's fetch resolves, or if it fails outright (e.g. the request is
blocked) - never updated again after this point, so they'll drift from
reality over time, but by then this live script is what's actually
driving the dropdown on every normal page load.
"""

import frappe

from dashboard.patches.create_student_resilience_survey_form import (
    WEB_FORM_ROUTE as RESILIENCE_WEB_FORM_ROUTE,
)
from dashboard.patches.create_stirling_wellbeing_scale_form import (
    WEB_FORM_ROUTE as STIRLING_WEB_FORM_ROUTE,
)

SCHOOL_OPTIONS_API = "dashboard.api.shared.school_client_options.get_school_client_names"

CLIENT_SCRIPT = """
(function () {
    function populate(select) {
        fetch("/api/method/""" + SCHOOL_OPTIONS_API + """")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var names = (data && data.message) || [];
                if (!names.length) { return; }

                var current = select.value;
                select.innerHTML = "";

                var blank = document.createElement("option");
                blank.value = "";
                select.appendChild(blank);

                names.forEach(function (name) {
                    var opt = document.createElement("option");
                    opt.value = name;
                    opt.textContent = name;
                    select.appendChild(opt);
                });

                if (names.indexOf(current) !== -1) {
                    select.value = current;
                }
            })
            .catch(function () {
                // Leave whatever options were already on the page -
                // a stale fallback list beats an empty dropdown.
            });
    }

    function tryFind() {
        var wrapper = document.querySelector('[data-fieldname="school"]');
        var select = wrapper ? wrapper.querySelector("select") : null;
        if (select) {
            populate(select);
            return true;
        }
        return false;
    }

    if (!tryFind()) {
        var attempts = 0;
        var interval = setInterval(function () {
            attempts += 1;
            if (tryFind() || attempts > 40) {
                clearInterval(interval);
            }
        }, 250);
    }
})();
""".strip()


def execute():
    _set_client_script(RESILIENCE_WEB_FORM_ROUTE)
    _set_client_script(STIRLING_WEB_FORM_ROUTE)


def _set_client_script(route):
    name = frappe.db.exists("Web Form", {"route": route})
    if not name:
        return

    doc = frappe.get_doc("Web Form", name)
    if (doc.client_script or "").strip() == CLIENT_SCRIPT:
        return

    doc.client_script = CLIENT_SCRIPT
    doc.save(ignore_permissions=True)
    frappe.db.commit()
