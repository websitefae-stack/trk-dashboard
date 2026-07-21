"""
Real UK postcode-district/area boundary polygons for the Client Locations
report's territory map - lets a coach's Territory Postcode Areas render as
actual postcode-shaped regions instead of an approximation built from
wherever their clients happen to live.

Source: github.com/missinglink/uk-postcode-polygons, itself an export of
Wikipedia's "List of postcode districts in the United Kingdom" boundary
maps, released under the Creative Commons Attribution-ShareAlike 3.0
Unported License - (c) Wikipedia contributors (see
data/uk_postcode_areas/ATTRIBUTION.md). One GeoJSON file per postcode area
(e.g. TW.geojson), with each district within that area as its own Feature.
Bundled locally so this never depends on a live fetch to a third party -
Northern Ireland (BT) and the Channel Islands/Isle of Man (GY/JE/IM) aren't
covered by the source dataset.
"""

import json
import os
import re

import frappe

_AREA_CODE_RE = re.compile(r"^[A-Z]{1,2}")
_area_feature_cache = {}


def _data_dir():
    return os.path.join(frappe.get_app_path("dashboard"), "data", "uk_postcode_areas")


def _area_code(prefix):
    """The postcode AREA (leading letters only) a district/sector prefix belongs to - "TW" from "TW9" or "TW9A"."""
    match = _AREA_CODE_RE.match((prefix or "").strip().upper())
    return match.group(0) if match else ""


def _load_area_features(area_code):
    if area_code in _area_feature_cache:
        return _area_feature_cache[area_code]

    features = []
    path = os.path.join(_data_dir(), f"{area_code}.geojson")

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features") or []
        except Exception:
            features = []

    _area_feature_cache[area_code] = features
    return features


def _matching_features(prefix, area_features):
    prefix = (prefix or "").strip().upper()

    exact = [f for f in area_features if (f.get("properties") or {}).get("name") == prefix]
    if exact:
        return exact

    # A sub-district code like "SW1A" isn't its own shape in this dataset
    # (district-level is as granular as it gets) - falls back to whichever
    # district it's actually part of.
    contains = [
        f for f in area_features
        if prefix and prefix.startswith((f.get("properties") or {}).get("name") or "\x00")
    ]
    if contains:
        return contains

    # An area-only code like "TW" (no district number) - every district in
    # that area.
    return [
        f for f in area_features
        if ((f.get("properties") or {}).get("name") or "").startswith(prefix)
    ]


def get_territory_features(prefixes):
    """
    Takes a coach's list of Territory Postcode Area prefixes (e.g. ["TW9",
    "SW1"]) and returns the matching GeoJSON Features (deduplicated by
    district name) covering all of them - an empty list if none of the
    prefixes matched anything in the bundled dataset (a typo, or a
    Northern Ireland/Crown Dependency code this free dataset doesn't have).
    """
    features_by_name = {}

    for prefix in prefixes or []:
        area_code = _area_code(prefix)
        if not area_code:
            continue

        area_features = _load_area_features(area_code)
        if not area_features:
            continue

        for feature in _matching_features(prefix, area_features):
            name = (feature.get("properties") or {}).get("name")
            if name:
                features_by_name[name] = feature

    return list(features_by_name.values())
