"""
One-off bulk import of Ashley's full Resilient Kid podcast back-
catalogue (89 episodes) from her own export (data/resilient_kid_
podcast_import.csv), to replace the handful of episodes that had
been entered manually before this with inconsistent/broken show
notes HTML.

Writes the Show Notes HTML straight into the Text Editor field via
the ORM, never through a browser paste - the exact thing that was
mangling tags/links on the manually-entered ones never touches this
path at all.

Ashley needs to delete every existing Podcast Episode record herself
first (Desk > Podcast Episode list > select all > Delete) - this
patch only ever creates rows, it never deletes or updates one, so
running it without clearing the old ones first would leave the old,
broken entries sitting alongside the new, correct ones rather than
being replaced. Safe to re-run after that: skips any row whose exact
Episode Title already exists as a Podcast Episode, rather than
creating a second copy.
"""

import csv
import os

import frappe

DOCTYPE = "Podcast Episode"
DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "resilient_kid_podcast_import.csv")
VALID_STATUSES = {"Planned", "Recorded", "Published"}


def _to_int(value):
	value = (value or "").strip()
	return int(value) if value.isdigit() else None


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	if not os.path.exists(DATA_FILE):
		return

	with open(DATA_FILE, encoding="utf-8", newline="") as f:
		rows = list(csv.DictReader(f))

	imported = 0

	for row in rows:
		title = (row.get("Episode Title") or "").strip()
		if not title:
			continue

		if frappe.db.exists(DOCTYPE, {"episode_title": title}):
			continue

		status = (row.get("Status") or "").strip()
		if status not in VALID_STATUSES:
			status = "Published"

		doc = frappe.new_doc(DOCTYPE)
		doc.episode_title = title
		doc.season_number = _to_int(row.get("Season #"))
		doc.episode_number = _to_int(row.get("Episode #"))
		doc.guest_name = (row.get("Guest (if any)") or "").strip()
		doc.status = status
		doc.air_date = (row.get("Air Date") or "").strip() or None
		doc.topics = (row.get("Topics") or "").strip()
		doc.show_notes = row.get("Show Notes") or ""
		doc.spotify_url = (row.get("Spotify Link") or "").strip()
		doc.youtube_url = (row.get("YouTube Link") or "").strip()
		doc.insert(ignore_permissions=True)
		imported += 1

	frappe.db.commit()
	frappe.logger().info(f"Imported {imported} Resilient Kid podcast episode(s).")
