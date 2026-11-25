# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea Finance Settings: everything Drea HR needs to send payroll totals to Drea Finance, kept
apart from HR's own settings (owner, 25 Nov 2026). Drea HR runs without it: with the connection
off, nothing here is used.

- Connection: address, API key, send on/off, Tests Only.
- Mappings: Company -> legal entity code, Department -> Division, Salary Component -> pay code.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

ENTITY_CODE = re.compile(r"^LE-\d{5}$")


class DreaFinanceSettings(Document):
	def validate(self):
		self.url = (self.url or "").strip().rstrip("/")
		self.check_unique("companies", "company", _("Company"))
		self.check_unique("departments", "department", _("Department"))
		self.check_unique("pay_codes", "salary_component", _("Salary Component"))
		self.check_entity_codes()
		self.check_divisions()
		self.check_pay_codes()

	def check_unique(self, table, field, label):
		seen = set()
		for row in self.get(table):
			value = row.get(field)
			if value in seen:
				frappe.throw(_("Row {0}: {1} {2} is listed twice.").format(row.idx, label, frappe.bold(value)))
			seen.add(value)

	def check_entity_codes(self):
		seen = {}
		for row in self.companies:
			row.entity_code = (row.entity_code or "").strip().upper()
			if not ENTITY_CODE.match(row.entity_code):
				frappe.throw(
					_("Row {0}: {1} is not a legal entity code. Use LE-00001 style codes from Drea Finance.").format(
						row.idx, frappe.bold(row.entity_code)
					)
				)
			if row.entity_code in seen:
				frappe.throw(
					_("{0} is given to both {1} and {2}.").format(
						frappe.bold(row.entity_code), seen[row.entity_code], row.company
					)
				)
			seen[row.entity_code] = row.company

	def check_divisions(self):
		for row in self.departments:
			if not frappe.db.get_value("Division", row.division, "is_active"):
				frappe.throw(
					_("Row {0}: Division {1} is not active in Drea Finance.").format(row.idx, frappe.bold(row.division))
				)

	def check_pay_codes(self):
		from hrms.payroll.drea_finance import ALLOWED_KINDS, CODE_KINDS

		for row in self.pay_codes:
			component_type = frappe.db.get_value("Salary Component", row.salary_component, "type")
			kind = CODE_KINDS.get(row.pay_code)
			if kind not in ALLOWED_KINDS.get(component_type, set()):
				frappe.throw(
					_("Row {0}: {1} is a {2} code in Drea Finance; {3} is a {4} component.").format(
						row.idx,
						frappe.bold(row.pay_code),
						kind or _("unknown"),
						frappe.bold(row.salary_component),
						_(component_type or ""),
					),
					title=_("Pay code"),
				)


def is_enabled() -> bool:
	"""True when Drea HR is connected to Drea Finance. False on a site without this page yet."""
	if not frappe.db.table_exists("Singles") or not frappe.db.exists("DocType", "Drea Finance Settings"):
		return False
	return bool(cint(frappe.db.get_single_value("Drea Finance Settings", "enabled")))


def mappings() -> dict:
	"""{"companies": {company: LE code}, "departments": {department: division}, "pay_codes": {component: code}}."""
	doc = frappe.get_cached_doc("Drea Finance Settings")
	return {
		"companies": {r.company: r.entity_code for r in doc.companies},
		"departments": {r.department: r.division for r in doc.departments},
		"pay_codes": {r.salary_component: r.pay_code for r in doc.pay_codes},
	}
