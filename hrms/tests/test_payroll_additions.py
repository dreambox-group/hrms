# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Payroll additions of 24 Nov 2026: the Net Pay column on a Payroll Entry's employees, Export
Salary Slips (CSV), and salary components found in lower case on Postgres."""

import csv
import io

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.payroll import salary_slip_export as export
from hrms.payroll.doctype.salary_structure.salary_structure import get_salary_component


class TestPayrollAdditions(IntegrationTestCase):
	def setUp(self):
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import TestPayrollEntry

		TestPayrollEntry.setUp(self)
		frappe.db.set_single_value("Payroll Settings", "email_salary_slip_to_employee", 0)

	def make_entry(self, prefix):
		"""A month's payroll for two new people (each test its own: an employee with a slip for
		the month is left out of the next entry)."""
		from hrms.payroll.doctype.payroll_entry.payroll_entry import get_start_end_dates
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import make_payroll_entry, setup_salary_structure

		company = frappe.get_doc("Company", "_Test Company")
		for i in (1, 2):
			setup_salary_structure(make_employee(f"pa.{prefix}{i}@example.com", company=company.name), company)
		dates = get_start_end_dates("Monthly", frappe.utils.nowdate())
		return make_payroll_entry(
			start_date=dates.start_date,
			end_date=dates.end_date,
			payable_account=company.default_payroll_payable_account,
			currency=company.default_currency,
			company=company.name,
			cost_center="Main - _TC",
		)

	def test_net_pay_column_follows_the_slips(self):
		entry = self.make_entry("net")
		slips = dict(
			frappe.get_all(
				"Salary Slip",
				filters={"payroll_entry": entry.name, "docstatus": 1},
				fields=["employee", "net_pay"],
				as_list=True,
			)
		)
		doc = frappe.get_doc("Payroll Entry", entry.name)
		doc.run_method("onload")
		self.assertTrue(doc.employees)
		for row in doc.employees:
			self.assertEqual(row.net_pay, slips[row.employee])

	def test_export_is_one_row_per_slip_with_a_column_per_component(self):
		entry = self.make_entry("csv")
		names = frappe.get_all("Salary Slip", filters={"payroll_entry": entry.name, "docstatus": 1}, pluck="name")
		frappe.local.response = frappe._dict()
		export.export_salary_slips(names=frappe.as_json(names))
		response = frappe.local.response
		self.assertEqual(response.type, "download")
		self.assertTrue(response.filename.endswith(".csv"))
		self.assertTrue(response.filecontent.startswith("﻿"))
		rows = list(csv.reader(io.StringIO(response.filecontent.lstrip("﻿"))))
		header, body = rows[0], rows[1:]
		self.assertEqual(len(body), len(names))
		for column in ("Employee", "Gross Pay", "Total Deduction", "Net Pay"):
			self.assertIn(column, header)
		for line in body:
			slip = frappe.get_doc("Salary Slip", line[0])
			self.assertEqual(float(line[header.index("Net Pay")]), slip.net_pay)
			for detail in slip.earnings:
				self.assertEqual(float(line[header.index(detail.salary_component)]), detail.amount)
		self.assertEqual(export.count_salary_slips_for_export(names=frappe.as_json(names)), len(names))

	def test_export_is_hr_only_and_leaves_out_cancelled_slips(self):
		self.assertEqual(export._text("=SUM(A1)"), "'=SUM(A1)")
		self.assertEqual(export._number(7333333.0), 7333333)
		filters = export._filters("[]", "[]")
		self.assertIn(["Salary Slip", "docstatus", "!=", 2], filters)
		user = "pa.nothr@example.com"
		make_employee(user, company="_Test Company")
		frappe.get_doc("User", user).remove_roles("HR Manager", "HR User", "System Manager")
		frappe.set_user(user)
		try:
			self.assertRaises(frappe.PermissionError, export.export_salary_slips, filters="[]", names="[]")
		finally:
			frappe.set_user("Administrator")

	def test_components_are_found_whatever_the_case(self):
		"""The form sends "earning" in lower case; Postgres compares with case (24 Nov 2026 fix)."""
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import setup_salary_structure

		company = frappe.get_doc("Company", "_Test Company")
		setup_salary_structure(make_employee("pa.case@example.com", company=company.name), company)
		filters = {"component_type": "earning", "company": company.name}
		found = [r[0] for r in get_salary_component("Salary Component", "", "name", 0, 50, filters)]
		earnings = frappe.get_all("Salary Component", filters={"type": "Earning", "disabled": 0}, pluck="name")
		self.assertTrue(found)
		self.assertTrue(set(found) <= set(earnings))
		some = found[0]
		typed = [r[0] for r in get_salary_component("Salary Component", some.upper(), "name", 0, 50, filters)]
		self.assertIn(some, typed)
