(function () {
    function el(id) {
        return document.getElementById(id);
    }

    function getCsrfToken() {
        var hidden = el("csrfToken");
        if (hidden && hidden.value) return hidden.value;
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta && meta.content ? meta.content : "";
    }

    async function apiCall(method, args) {
        var response = await fetch("/api/method/dashboard.api.shared.supervision_booking." + method, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Frappe-CSRF-Token": getCsrfToken(),
            },
            body: JSON.stringify(args || {}),
        });
        var data = {};
        try {
            data = await response.json();
        } catch (error) {
            throw new Error("Could not read server response.");
        }
        if (!response.ok || data.exc) {
            throw new Error(data.message || "Request failed.");
        }
        return data.message;
    }

    function showMessage(widget, text, isError) {
        var message = widget.querySelector("[data-supervision-message]");
        if (!message) return;
        message.textContent = text;
        message.style.display = text ? "block" : "none";
        message.style.color = isError ? "#c0392b" : "";
    }

    function renderSlots(widget, slots, date) {
        var container = widget.querySelector("[data-supervision-slots]");
        if (!container) return;

        if (!slots.length) {
            container.innerHTML = '<p class="dashboard-empty">No available times on this date - try another day.</p>';
            return;
        }

        container.innerHTML = slots.map(function (slot) {
            return '<button type="button" class="dashboard-btn dashboard-btn-light" data-supervision-slot="' + slot + '" style="margin-right:8px; margin-bottom:8px;">' + slot + '</button>';
        }).join("");

        container.querySelectorAll("[data-supervision-slot]").forEach(function (button) {
            button.addEventListener("click", function () {
                confirmBooking(widget, date, button.dataset.supervisionSlot);
            });
        });
    }

    function checkAvailability(widget) {
        var coach = widget.dataset.supervisionCoach;
        var dateInput = widget.querySelector("[data-supervision-date]");
        var container = widget.querySelector("[data-supervision-slots]");

        if (!coach || !dateInput || !dateInput.value) return;

        showMessage(widget, "", false);
        if (container) container.innerHTML = '<p class="dashboard-empty">Checking availability...</p>';

        apiCall("get_supervision_slots", { coach: coach, date: dateInput.value }).then(function (slots) {
            renderSlots(widget, slots || [], dateInput.value);
        }).catch(function () {
            if (container) container.innerHTML = '<p class="dashboard-empty">Unable to check availability.</p>';
        });
    }

    function confirmBooking(widget, date, time) {
        var coach = widget.dataset.supervisionCoach;
        if (!coach) return;

        if (!window.confirm("Book Supervision for " + date + " at " + time + "?")) return;

        apiCall("book_supervision", { coach: coach, date: date, time: time }).then(function () {
            showMessage(widget, "Booked! You'll get a confirmation for this session.", false);
            var container = widget.querySelector("[data-supervision-slots]");
            if (container) container.innerHTML = "";
        }).catch(function (error) {
            showMessage(widget, (error && error.message) || "Unable to book this slot.", true);
        });
    }

    function initWidget(widget) {
        var checkButton = widget.querySelector("[data-supervision-check]");
        if (checkButton) {
            checkButton.addEventListener("click", function () {
                checkAvailability(widget);
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".supervision-booking-widget").forEach(initWidget);
    });
})();
