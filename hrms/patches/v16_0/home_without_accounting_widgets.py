# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""No accounting figures on the desk's Home page (owner, 25 and 26 Nov 2026).

ERPNext's Home page (Setup > Home) shows a Profit and Loss chart and the cards Annual Sales,
Annual Purchase and Total Stock Value. Accounting lives in Drea Finance, not here, so they
would always show zero; and the chart's report asks the database with "FORCE INDEX", which
only MySQL understands, so on Postgres it failed on every visit with an error.

The page belongs to ERPNext (erpnext/setup/workspace/home/home.json). Frappe loads that file
again only when an ERPNext update changes it; if these come back after such an update, run
this patch again (bench --site <site> execute
hrms.patches.v16_0.home_without_accounting_widgets.execute).
"""

import json

import frappe

CHARTS = ("Profit and Loss",)
NUMBER_CARDS = ("Annual Sales", "Annual Purchase", "Total Stock Value")


def _unwanted(block: dict) -> bool:
	data = block.get("data") or {}
	if block.get("type") == "chart":
		return data.get("chart_name") in CHARTS
	if block.get("type") == "number_card":
		return data.get("number_card_name") in NUMBER_CARDS
	return False


def execute():
	if not frappe.db.exists("Workspace", "Home"):
		return

	content = frappe.db.get_value("Workspace", "Home", "content") or "[]"
	try:
		blocks = json.loads(content)
	except ValueError:
		return

	kept = [block for block in blocks if not _unwanted(block)]
	if len(kept) != len(blocks):
		frappe.db.set_value("Workspace", "Home", "content", json.dumps(kept), update_modified=False)

	frappe.db.delete("Workspace Chart", {"parent": "Home", "parenttype": "Workspace", "chart_name": ("in", CHARTS)})
	frappe.db.delete(
		"Workspace Number Card",
		{"parent": "Home", "parenttype": "Workspace", "number_card_name": ("in", NUMBER_CARDS)},
	)
	frappe.clear_cache()
