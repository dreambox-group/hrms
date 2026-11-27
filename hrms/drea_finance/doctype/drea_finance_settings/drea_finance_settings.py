# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea Finance Settings: everything Drea HR needs to send payroll totals to Drea Finance, kept
apart from HR's own settings (owner, 25 Nov 2026). Drea HR runs without it: with the connection
off, nothing here is used.

- Connection: address, API key, send on/off, Tests Only.
- Mappings: Company -> legal entity code, Department -> Division, Salary Component -> pay code.
- Pay codes -> Drea Finance accounts (owner, 27 Nov 2026): Drea Finance keeps no salary settings;
  this table goes with every payroll and Drea Finance checks the accounts against its chart.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

ENTITY_CODE = re.compile(r"^LE-\d{5}$")
PAY_CODE = re.compile(r"^[A-Z][A-Z0-9_]{1,39}$")  # Drea Finance's rule
ACCOUNT_CODE = re.compile(r"^\d{6}$")
# which accounts each kind of pay code books to: (account, owed account)
ACCOUNTS_FOR_KIND = {
	"earning": (True, False),  # pay: a cost account, or 310200 for partners' prive
	"deduction": (False, True),  # taken from pay, owed to someone (tax, BPJS)
	"employer": (True, True),  # paid by the company on top: a cost, owed to BPJS or the tax office
}


class DreaFinanceSettings(Document):
	def validate(self):
		self.url = (self.url or "").strip().rstrip("/")
		self.check_unique("companies", "company", _("Company"))
		self.check_unique("departments", "department", _("Department"))
		self.check_unique("pay_codes", "salary_component", _("Salary Component"))
		self.check_entity_codes()
		self.check_divisions()
		self.check_codes()
		self.check_pay_codes()

	def check_unique(self, table, field, label):
		seen = set()
		for row in self.get(table):
			value = row.get(field)
			if value in seen:
				frappe.throw(
					_("Row {0}: {1} {2} is listed twice.").format(row.idx, label, frappe.bold(value))
				)
			seen.add(value)

	def check_entity_codes(self):
		seen = {}
		for row in self.companies:
			row.entity_code = (row.entity_code or "").strip().upper()
			if not ENTITY_CODE.match(row.entity_code):
				frappe.throw(
					_(
						"Row {0}: {1} is not a legal entity code. Use LE-00001 style codes from Drea Finance."
					).format(row.idx, frappe.bold(row.entity_code))
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
					_("Row {0}: Division {1} is not active in Drea Finance.").format(
						row.idx, frappe.bold(row.division)
					)
				)

	def check_codes(self):
		seen = set()
		for row in self.codes:
			row.pay_code = (row.pay_code or "").strip().upper()
			row.code_name = (row.code_name or "").strip()
			row.account = (row.account or "").strip()
			row.owed_account = (row.owed_account or "").strip()
			code = frappe.bold(row.pay_code)
			if not PAY_CODE.match(row.pay_code):
				frappe.throw(
					_(
						"Row {0}: {1} is not a pay code. Use capital letters, digits and _, e.g. SALARY."
					).format(row.idx, code),
					title=_("Pay code"),
				)
			if row.pay_code in seen:
				frappe.throw(_("Pay code {0} is listed twice.").format(code), title=_("Pay code"))
			seen.add(row.pay_code)
			if row.kind not in ACCOUNTS_FOR_KIND:
				frappe.throw(
					_("Row {0}: choose what {1} is: earning, deduction or employer.").format(row.idx, code),
					title=_("Pay code"),
				)
			wants_account, wants_owed = ACCOUNTS_FOR_KIND[row.kind]
			for field, label, wanted in (
				("account", _("Account"), wants_account),
				("owed_account", _("Owed Account"), wants_owed),
			):
				value = row.get(field)
				if wanted and not value:
					frappe.throw(
						_("Row {0}: {1} is a {2} code; it needs the {3}.").format(
							row.idx, code, row.kind, label
						),
						title=_("Pay code"),
					)
				if not wanted and value:
					frappe.throw(
						_("Row {0}: {1} is a {2} code; leave {3} empty.").format(
							row.idx, code, row.kind, label
						),
						title=_("Pay code"),
					)
				if value and not ACCOUNT_CODE.match(value):
					frappe.throw(
						_(
							"Row {0}: {1} {2} must be a Drea Finance account code, six digits (e.g. 510201)."
						).format(row.idx, code, label),
						title=_("Pay code"),
					)

	def check_pay_codes(self):
		from hrms.payroll.drea_finance import ALLOWED_KINDS

		kinds = {row.pay_code: row.kind for row in self.codes}
		for row in self.pay_codes:
			row.pay_code = (row.pay_code or "").strip().upper()
			component_type = frappe.db.get_value("Salary Component", row.salary_component, "type")
			kind = kinds.get(row.pay_code)
			if not kind:
				frappe.throw(
					_("Row {0}: pay code {1} is not in Pay Codes → Drea Finance Accounts.").format(
						row.idx, frappe.bold(row.pay_code)
					),
					title=_("Pay code"),
				)
			if kind not in ALLOWED_KINDS.get(component_type, set()):
				frappe.throw(
					_("Row {0}: {1} is a {2} code; {3} is a {4} component.").format(
						row.idx,
						frappe.bold(row.pay_code),
						kind,
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
	"""{"companies": {company: LE code}, "departments": {department: division},
	"pay_codes": {component: code}, "codes": {code: {"name", "kind", "account", "owed_account"}}}."""
	doc = frappe.get_cached_doc("Drea Finance Settings")
	return {
		"companies": {r.company: r.entity_code for r in doc.companies},
		"departments": {r.department: r.division for r in doc.departments},
		"pay_codes": {r.salary_component: r.pay_code for r in doc.pay_codes},
		"codes": {
			r.pay_code: {
				"name": r.code_name or r.pay_code,
				"kind": r.kind,
				"account": r.account or None,
				"owed_account": r.owed_account or None,
			}
			for r in doc.codes
		},
	}
