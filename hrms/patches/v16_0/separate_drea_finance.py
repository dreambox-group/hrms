"""Separate Drea Finance from Drea HR (owner, 25 Nov 2026).

Drea HR runs on its own and only sends payroll totals to Drea Finance. What the one-database plan
of 2 Nov 2026 put on HR's own forms moves out:

- kept, moved into Drea Finance Settings: the connection (address, API key, send switch, Tests
  Only) from HR Settings, and the mappings Company -> legal entity code, Department -> Division,
  Salary Component -> pay code;
- dropped, but first saved to a private file (Files, "drea_finance_separation_*.json"): the
  Finance users' roles and divisions, the Company tax fields, the service-account list and the
  Drea One reimbursement switches.

Then the old custom fields go (hrms.setup.setup_drea_finance) and the User Division table with them.
"""

import json

import frappe
from frappe.utils import cint, now_datetime
from frappe.utils.password import get_decrypted_password

HR_SETTINGS_FIELDS = (
	"drea_finance_url",
	"drea_finance_send_payroll",
	"drea_finance_payroll_test_only",
	"show_reimbursements_in_employee_app",
	"drea_finance_paused",
	"drea_finance_no_password_users",
)
COMPANY_FIELDS = (
	"drea_finance_code",
	"drea_finance_display_name",
	"drea_finance_active",
	"books_start_date",
	"is_pkp",
	"pkp_since",
	"withholding_tax_percent",
	"withholding_kind",
)
USER_FIELDS = ("drea_finance_role", "drea_finance_active")


def execute():
	if frappe.db.get_value(
		"Custom Field", {"dt": "Company", "fieldname": "drea_finance_code"}
	) is None and not (frappe.db.has_column("Company", "drea_finance_code")):
		finish()
		return

	old = read_old_values()
	save_export(old)
	fill_settings(old)
	finish()


def column_values(doctype, fields):
	have = [f for f in fields if frappe.db.has_column(doctype, f)]
	if not have:
		return {}
	return {r.name: {f: r.get(f) for f in have} for r in frappe.get_all(doctype, fields=["name", *have])}


def read_old_values() -> dict:
	singles = dict(
		frappe.db.sql(
			"""select field, value from "tabSingles" where doctype = 'HR Settings' and field in %s""",
			[HR_SETTINGS_FIELDS],
		)
	)
	try:
		api_key = get_decrypted_password(
			"HR Settings", "HR Settings", "drea_finance_api_key", raise_exception=False
		)
	except Exception:
		api_key = None
	users = {
		name: values
		for name, values in column_values("User", USER_FIELDS).items()
		if any(v not in (None, "", 0) for v in values.values())
	}
	if frappe.db.table_exists("User Division"):
		for row in frappe.get_all(
			"User Division", filters={"parenttype": "User"}, fields=["parent", "division"]
		):
			users.setdefault(row.parent, {}).setdefault("divisions", []).append(row.division)
	return {
		"hr_settings": singles,
		"api_key": api_key,
		"companies": column_values("Company", COMPANY_FIELDS),
		"departments": {
			k: v.get("drea_finance_division")
			for k, v in column_values("Department", ("drea_finance_division",)).items()
			if v.get("drea_finance_division")
		},
		"pay_codes": {
			k: v.get("drea_finance_component")
			for k, v in column_values("Salary Component", ("drea_finance_component",)).items()
			if v.get("drea_finance_component")
		},
		"users": users,
	}


def save_export(old):
	"""Everything that leaves HR's forms, kept as a private file (the API key is left out)."""
	export = {k: v for k, v in old.items() if k != "api_key"}
	export["saved_on"] = str(now_datetime())
	name = f"drea_finance_separation_{now_datetime().strftime('%Y%m%d_%H%M%S')}.json"
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": name,
			"is_private": 1,
			"content": json.dumps(export, indent=1, default=str),
		}
	).insert(ignore_permissions=True)


def fill_settings(old):
	settings = frappe.get_single("Drea Finance Settings")
	hr = old["hr_settings"]
	url = (hr.get("drea_finance_url") or "").strip()
	if url and not settings.url:
		settings.url = url
		settings.enabled = 1
		settings.send_payroll = cint(hr.get("drea_finance_send_payroll"))
		# the payroll message changed with the separation (components, rows and people): the first
		# send after it is a test, whatever the old switch said; the owner turns Tests Only off
		settings.test_only = 1
		if old["api_key"]:
			settings.api_key = old["api_key"]

	have = {r.company for r in settings.companies}
	for company, values in sorted(old["companies"].items()):
		code = (values.get("drea_finance_code") or "").strip()
		if code and company not in have:
			settings.append("companies", {"company": company, "entity_code": code})
	have = {r.department for r in settings.departments}
	for department, division in sorted(old["departments"].items()):
		if department not in have and frappe.db.get_value("Division", division, "is_active"):
			settings.append("departments", {"department": department, "division": division})
	have = {r.salary_component for r in settings.pay_codes}
	for component, code in sorted(old["pay_codes"].items()):
		if component not in have:
			settings.append("pay_codes", {"salary_component": component, "pay_code": code})
	settings.flags.ignore_mandatory = True
	# the old mappings move as they are: the pay code accounts table they are checked against is
	# filled later by hrms.payroll.drea_payroll_setup, which also drops the codes Drea Finance no
	# longer has (production, 28 Nov 2026: 17 old mappings and no accounts table yet)
	settings.flags.ignore_validate = True
	settings.save(ignore_permissions=True)


def finish():
	from hrms.setup import setup_drea_finance

	setup_drea_finance()  # drops the retired custom fields
	if frappe.db.exists("DocType", "User Division"):
		frappe.delete_doc("DocType", "User Division", ignore_permissions=True, force=True)
	frappe.db.delete(
		"Singles", {"doctype": "HR Settings", "field": ("in", [*HR_SETTINGS_FIELDS, "drea_finance_api_key"])}
	)
	frappe.db.delete("__Auth", {"doctype": "HR Settings", "fieldname": "drea_finance_api_key"})
	frappe.clear_cache()
