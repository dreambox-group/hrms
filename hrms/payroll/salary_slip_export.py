# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Export Salary Slips (CSV), from the Salary Slip list's menu (owner, 24 Nov 2026).

One row per slip: who, which period and status, then every earning, Gross Pay, every deduction,
Total Deduction, Net Pay and the company's contributions (BPJS Perusahaan), each component its own
column. The ticked slips, or with none ticked every slip the list's filters show. Cancelled slips
are left out. HR only; the slips go through the person's own read permission (frappe.get_list).

UTF-8 with a byte-order mark so Excel reads the names right. Numbers are plain (no thousands
separator), dates YYYY-MM-DD.
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

HR_ROLES = ("HR Manager", "HR User", "System Manager")
SECTIONS = ("earnings", "deductions", "employer_contributions")
SLIP_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"company",
	"department",
	"designation",
	"payroll_entry",
	"start_date",
	"end_date",
	"posting_date",
	"status",
	"total_working_days",
	"payment_days",
	"gross_pay",
	"total_deduction",
	"net_pay",
]


def _filters(filters, names):
	names = frappe.parse_json(names) or []
	filters = frappe.parse_json(filters) or []
	if names:
		filters = [["Salary Slip", "name", "in", names]]
	if isinstance(filters, dict):
		filters = [["Salary Slip", key, "=", value] for key, value in filters.items()]
	return [*filters, ["Salary Slip", "docstatus", "!=", 2]]


def _slips(filters, names, fields):
	return frappe.get_list(
		"Salary Slip",
		filters=_filters(filters, names),
		fields=fields,
		order_by="start_date desc, employee_name asc",
		limit_page_length=0,
	)


@frappe.whitelist()
def count_salary_slips_for_export(filters=None, names=None) -> int:
	frappe.only_for(HR_ROLES)
	return len(_slips(filters, names, ["name"]))


def _text(value):
	"""A text cell Excel would read as a formula (=, +, -, @) gets a leading apostrophe."""
	value = "" if value is None else str(value)
	return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _number(value):
	"""Whole rupiah as 7333333, not 7333333.0; cents kept when there are any."""
	value = flt(value, 2)
	return int(value) if value == int(value) else value


@frappe.whitelist()
def export_salary_slips(filters=None, names=None):
	frappe.only_for(HR_ROLES)
	slips = _slips(filters, names, SLIP_FIELDS)
	if not slips:
		frappe.throw(_("No salary slips to export: none are ticked or match the list's filters."))

	amounts = {}  # (slip, section, component) -> amount
	columns = {section: [] for section in SECTIONS}  # components in the order they first appear
	slip_names = [s.name for s in slips]
	for start in range(0, len(slip_names), 500):
		for row in frappe.get_all(
			"Salary Detail",
			filters={
				"parenttype": "Salary Slip",
				"parent": ["in", slip_names[start : start + 500]],
				"parentfield": ["in", SECTIONS],
			},
			fields=["parent", "parentfield", "salary_component", "amount"],
			order_by="idx asc",
		):
			key = (row.parent, row.parentfield, row.salary_component)
			amounts[key] = amounts.get(key, 0) + flt(row.amount)
			if row.salary_component not in columns[row.parentfield]:
				columns[row.parentfield].append(row.salary_component)

	header = [
		_("Salary Slip"),
		_("Employee"),
		_("Employee Name"),
		_("Company"),
		_("Department"),
		_("Designation"),
		_("Payroll Entry"),
		_("Start Date"),
		_("End Date"),
		_("Posting Date"),
		_("Status"),
		_("Working Days"),
		_("Payment Days"),
		*columns["earnings"],
		_("Gross Pay"),
		*columns["deductions"],
		_("Total Deduction"),
		_("Net Pay"),
		*[_("{0} (Employer)").format(c) for c in columns["employer_contributions"]],
	]

	out = io.StringIO()
	writer = csv.writer(out, lineterminator="\r\n")
	writer.writerow(header)
	for s in slips:

		def section(name, slip=s):
			return [_number(amounts.get((slip.name, name, c), 0)) for c in columns[name]]

		writer.writerow(
			[
				_text(s.name),
				_text(s.employee),
				_text(s.employee_name),
				_text(s.company),
				_text(s.department),
				_text(s.designation),
				_text(s.payroll_entry),
				s.start_date or "",
				s.end_date or "",
				s.posting_date or "",
				_text(_(s.status)),
				_number(s.total_working_days),
				_number(s.payment_days),
				*section("earnings"),
				_number(s.gross_pay),
				*section("deductions"),
				_number(s.total_deduction),
				_number(s.net_pay),
				*section("employer_contributions"),
			]
		)

	frappe.response["type"] = "download"
	frappe.response["filename"] = f"salary-slips-{now_datetime().strftime('%Y%m%d-%H%M')}.csv"
	frappe.response["filecontent"] = "﻿" + out.getvalue()
