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
				{"parent": "Drea Finance Settings", "salary_component": "BPJS JHT"},
				"pay_code",
			),
			"BPJS_TK_COMPANY",
		)
		# the company pays the employee's BPJS shares: no BPJS deduction is left
		for name in ("BPJS Kesehatan Karyawan", "BPJS JHT Karyawan", "BPJS JP Karyawan"):
			if frappe.db.exists("Salary Component", name):
				self.assertEqual(frappe.db.get_value("Salary Component", name, "disabled"), 1)
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
		employee = make_employee(
			"drea.payroll.setup@example.com", company=COMPANY, date_of_joining="2025-01-01"
		)
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
		# BPJS is on the full monthly wage, whatever the days worked; the company pays all of it,
		# its own share and the employee's
		self.assertEqual(amounts["BPJS Kesehatan"], 600_000)  # 5% of the 12,000,000 cap
		self.assertEqual(amounts["BPJS JHT"], 855_000)  # 5.7%
		self.assertEqual(amounts["BPJS JP"], round(setup.JP_WAGE_CAP * 0.03))  # 3% of the cap
		self.assertEqual([r.salary_component for r in slip.deductions], [])  # nothing taken from pay
		if full:
			self.assertEqual(slip.net_pay, 15_000_000)
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

	def test_prive_codes(self):
		from hrms.payroll.drea_finance import code_kind

		self.assertEqual(code_kind("PRIVE_ALAND"), "earning")
		self.assertEqual(code_kind("SALARY"), "earning")
		self.assertIsNone(code_kind("PRIVE_"))
		self.assertIsNone(code_kind("PRIVE_aland"))
		self.assertIsNone(code_kind("SOMETHING_ELSE"))

	def test_leader_paid_by_prive(self):
		from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
		from hrms.payroll.doctype.salary_structure.test_salary_structure import (
			create_salary_structure_assignment,
		)

		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		employee = make_employee("drea.leader@example.com", company=COMPANY, date_of_joining="2025-01-01")
		name = frappe.db.get_value("Employee", employee, "employee_name")
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")

		self.assertEqual(frappe.db.count("Salary Structure", {"name": f"Drea Leader - {name} - {abbr}"}), 0)
		lines = setup.add_leader(employee, "prive_test_leader", dry_run=False, commit=False)
		self.assertTrue(lines)
		component = f"Prive {name}"
		self.assertEqual(frappe.db.get_value("Salary Component", component, "type"), "Earning")
		self.assertEqual(frappe.get_doc("Salary Component", component).accounts[0].account, f"Prive - {abbr}")
		self.assertEqual(frappe.db.get_value("Account", f"Prive - {abbr}", "root_type"), "Equity")
		self.assertEqual(
			frappe.db.get_value(
				"Drea Finance Pay Code",
				{"parent": "Drea Finance Settings", "salary_component": component},
				"pay_code",
			),
			"PRIVE_TEST_LEADER",
		)
		# a second run finds nothing to do
		self.assertEqual(setup.add_leader(employee, "PRIVE_TEST_LEADER", dry_run=True), [])

		structure = frappe.get_doc("Salary Structure", f"Drea Leader - {name} - {abbr}")
		structure.submit()
		create_salary_structure_assignment(
			employee, structure.name, company=COMPANY, base=20_000_000, from_date="2025-01-01"
		)
		slip = make_salary_slip(structure.name, employee=employee)
		lines = {
			row.salary_component: row.amount
			for table in ("earnings", "deductions", "employer_contributions")
			for row in slip.get(table)
		}
		self.assertEqual(lines, {component: 20_000_000})  # no BPJS, PPh 21 or cuts on a drawing
		self.assertEqual(slip.net_pay, 20_000_000)

	def test_prive_code_only_on_an_earning(self):
		settings = frappe.get_single("Drea Finance Settings")
		settings.append("pay_codes", {"salary_component": "Late Penalty", "pay_code": "PRIVE_SOMEONE"})
		settings.flags.ignore_mandatory = True
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

	def test_pay_sheet_reading(self):
		from hrms.payroll.drea_pay_sheet import prive_code_for, ptkp_from

		self.assertEqual(ptkp_from("Belum Menikah"), "TK/0")
		self.assertEqual(ptkp_from("Menikah, K/2"), "K/2")
		self.assertEqual(ptkp_from("Menikah"), "K/0")
		self.assertEqual(ptkp_from("TK/1"), "TK/1")
		self.assertIsNone(ptkp_from(""))
		self.assertIsNone(ptkp_from("Cerai"))
		self.assertEqual(prive_code_for("Andreas Kevin Adam"), "PRIVE_ANDREAS")
		self.assertEqual(prive_code_for("Aland Sinduartha Tjandra"), "PRIVE_ALAND")
