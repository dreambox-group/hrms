# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Drea payroll setup (hrms.payroll.drea_payroll_setup): components, their Drea Finance pay codes
and accounts, the retired components, the draft structure and the BPJS amounts on a real slip."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.payroll import drea_payroll_setup as setup
from hrms.payroll.drea_finance import ALLOWED_KINDS, CODE_KINDS

COMPANY = "_Test Company"


class TestDreaPayrollSetup(IntegrationTestCase):
	def setUp(self):
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import TestPayrollEntry

		TestPayrollEntry.setUp(self)
		frappe.db.set_single_value("Payroll Settings", "email_salary_slip_to_employee", 0)

	def test_every_code_fits_its_component_type(self):
		for name, (_abbr, component_type, _formula, code, _days, _taxable) in setup.COMPONENTS.items():
			self.assertIn(CODE_KINDS[code], ALLOWED_KINDS[component_type], name)

	def test_retires_components_and_stops_counting_holidays(self):
		for name in ("Income Tax", "PPh23"):
			if not frappe.db.exists("Salary Component", name):
				frappe.get_doc(
					{"doctype": "Salary Component", "salary_component": name, "type": "Deduction"}
				).insert()
			frappe.db.set_value("Salary Component", name, "disabled", 0)
		if not frappe.db.exists("Leave Type", "Sick Leave"):
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": "Sick Leave"}).insert()
		frappe.db.set_value("Leave Type", "Sick Leave", "include_holiday", 1)

		setup.apply(dry_run=False, companies=[COMPANY], commit=False)

		self.assertEqual(frappe.db.get_value("Salary Component", "Income Tax", "disabled"), 1)
		self.assertEqual(frappe.db.get_value("Salary Component", "PPh23", "disabled"), 1)
		self.assertEqual(frappe.db.get_value("Leave Type", "Sick Leave", "include_holiday"), 0)
		# the pay code goes to the Drea Finance mapping, not onto the component
		self.assertEqual(
			frappe.db.get_value(
				"Drea Finance Pay Code",
				{"parent": "Drea Finance Settings", "salary_component": "BPJS JHT Karyawan"},
				"pay_code",
			),
			"BPJS_TK_EMPLOYEE",
		)
		pph21 = frappe.get_doc("Salary Component", "PPh21")
		self.assertIn(COMPANY, {row.company for row in pph21.accounts})
		# a second run finds nothing to do
		self.assertEqual(setup.apply(dry_run=True, companies=[COMPANY]), [])

	def test_dry_run_saves_nothing(self):
		frappe.db.set_value("Leave Type", "Sick Leave", "include_holiday", 1) if frappe.db.exists(
			"Leave Type", "Sick Leave"
		) else None
		lines = setup.apply(dry_run=True, companies=[COMPANY])
		if frappe.db.exists("Leave Type", "Sick Leave"):
			self.assertIn("Leave Type Sick Leave: stop counting holidays as leave days", lines)
			self.assertEqual(frappe.db.get_value("Leave Type", "Sick Leave", "include_holiday"), 1)

	def test_bpjs_on_a_slip_with_the_caps(self):
		employee = make_employee("drea.payroll.setup@example.com", company=COMPANY, date_of_joining="2025-01-01")
		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		structure = frappe.get_doc("Salary Structure", f"Drea Full-time - {abbr}")
		if structure.docstatus == 0:
			structure.submit()

		from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
		from hrms.payroll.doctype.salary_structure.test_salary_structure import (
			create_salary_structure_assignment,
		)

		# from before the period: the pay calendar's period to pay now may start last month
		create_salary_structure_assignment(
			employee, structure.name, company=COMPANY, base=15_000_000, from_date="2025-01-01"
		)
		slip = make_salary_slip(structure.name, employee=employee)
		amounts = {row.salary_component: row.amount for row in slip.earnings + slip.deductions}
		amounts.update({row.salary_component: row.amount for row in slip.employer_contributions})
		full = slip.payment_days == slip.total_working_days
		if full:
			self.assertEqual(amounts["Basic"], 15_000_000)
		# BPJS is on the full monthly wage, whatever the days worked
		self.assertEqual(amounts["BPJS Kesehatan Karyawan"], 120_000)  # 1% of the 12,000,000 cap
		self.assertEqual(amounts["BPJS JHT Karyawan"], 300_000)  # 2%
		self.assertEqual(amounts["BPJS JP Karyawan"], round(setup.JP_WAGE_CAP * 0.01))  # 1% of the cap
		self.assertEqual(amounts["BPJS Kesehatan"], 480_000)
		self.assertEqual(amounts["BPJS JHT"], 555_000)
		self.assertEqual(amounts["BPJS JP"], round(setup.JP_WAGE_CAP * 0.02))
		self.assertEqual(amounts["BPJS JKM"], 45_000)
		self.assertEqual(amounts["BPJS JKK"], 36_000)
		self.assertNotIn("PPh21", amounts)  # Calculate PPh 21 is off, and a 0 line is removed
		self.assertNotIn("Unpaid Leave", amounts)  # no unpaid days

	def test_structures_and_pay_calendar(self):
		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		intern = frappe.get_doc("Salary Structure", f"Drea Intern - {abbr}")
		self.assertEqual([r.salary_component for r in intern.deductions], ["Unpaid Leave", "Late Penalty"])
		self.assertEqual([r.salary_component for r in intern.employer_contributions], ["PPh21"])
		full = frappe.get_doc("Salary Structure", f"Drea Full-time - {abbr}")
		self.assertIn("PPh21", [r.salary_component for r in full.employer_contributions])
		self.assertNotIn("PPh21", [r.salary_component for r in full.deductions])
		self.assertEqual(frappe.db.get_value("Salary Component", "PPh21", "type"), "Employer Contribution")
		self.assertEqual(frappe.db.get_single_value("HR Settings", "pay_period_start_day"), 19)
		self.assertEqual(frappe.db.get_single_value("HR Settings", "pay_day"), 27)
		self.assertEqual(
			frappe.db.get_value(
				"Drea Finance Pay Code",
				{"parent": "Drea Finance Settings", "salary_component": "THR"},
				"pay_code",
			),
			"INCENTIVE",
		)
