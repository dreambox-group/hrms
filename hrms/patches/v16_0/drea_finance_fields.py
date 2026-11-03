"""Drea Finance in the same database (decision of 2 Nov 2026): the Finance fields on User, Company
and Department, the Finance Admin role, the permission levels, and Dreambox's own divisions and
company codes (from Finance's payroll guide of 27 Oct 2026)."""

import frappe

from hrms.setup import setup_drea_finance

DIVISIONS = [
	("DV-00001", "Holding"),
	("DV-00002", "Digital"),
	("DV-00003", "Creator Led"),
	("DV-00004", "Shoot by Code"),
	("DV-00005", "LittleBit"),
	("DV-00006", "Reagentive"),
	("DV-00007", "Mind Sequence"),
	("DV-00008", "Website"),
	("SHARED", "Support staff (shared cost)"),
]

COMPANY_CODES = {
	"CV Dreambox Creative Multivisi": "LE-00001",
	"CV Dreambox Denalo International": "LE-00002",
	"CV Dreambox Creative Multitalenta": "LE-00003",
	"CV Kotak Mimpi Creative": "LE-00004",
}


def execute():
	setup_drea_finance()
	seed_dreambox_divisions_and_codes()


def seed_dreambox_divisions_and_codes():
	"""Dreambox's own data. A client site without these companies gets nothing seeded; its
	divisions and codes come from its own Drea Finance."""
	if not any(frappe.db.exists("Company", name) for name in COMPANY_CODES):
		return

	for order, (code, label) in enumerate(DIVISIONS, start=1):
		if frappe.db.exists("Division", code):
			continue
		frappe.get_doc(
			{
				"doctype": "Division",
				"division_code": code,
				"division_name": label,
				"is_active": 1,
				"display_order": order,
			}
		).insert(ignore_permissions=True)

	for company, code in COMPANY_CODES.items():
		if not frappe.db.exists("Company", company):
			continue
		if frappe.db.get_value("Company", company, "drea_finance_code"):
			continue
		if frappe.db.exists("Company", {"drea_finance_code": code}):
			continue
		frappe.db.set_value("Company", company, "drea_finance_code", code, update_modified=False)
