"""
One-off bulk import of Ashley's Resilient Kid podcast episodes for
Seasons 1-3 and Seasons 12-13 (47 episodes), from her own export
(data/resilient_kid_podcast_import_seasons_1_3_12_13.csv). Separate
data file and patch from the earlier Seasons 4-11 import (data/
resilient_kid_podcast_import.csv) - these season ranges don't
overlap with that one.

Every episode's Show Notes HTML in the source file was normalised
before being committed here so it ends with exactly one consistent
closing credit paragraph:

    The Resilient Kid Podcast is produced by Chantelle Venter at
    maddatu.com on behalf of The Resilient People, trading as The
    Resilient Kid, The Resilient Teen and The Resilient School.

(replacing whatever inconsistent "Produced by..." line, if any, was
already at the end of a given episode's notes).

Writes the Show Notes HTML straight into the Text Editor field via
the ORM, never through a browser paste. Safe to re-run: skips any
row whose exact Episode Title already exists as a Podcast Episode,
rather than creating a second copy.
"""

import csv
import os

import frappe

DOCTYPE = "Podcast Episode"
DATA_FILE = os.path.join(
	os.path.dirname(__file__), "data", "resilient_kid_podcast_import_seasons_1_3_12_13.csv"
)
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
	frappe.logger().info(f"Imported {imported} Resilient Kid podcast episode(s) (Seasons 1-3, 12-13).")
