# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Drea payroll setup (hrms.payroll.drea_payroll_setup): components with their Drea Finance codes
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
		frappe.db.set_single_value("HR Settings", "drea_finance_send_payroll", 0)

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

		setup.apply(dry_run=False, companies=[COMPANY])

		self.assertEqual(frappe.db.get_value("Salary Component", "Income Tax", "disabled"), 1)
		self.assertEqual(frappe.db.get_value("Salary Component", "PPh23", "disabled"), 1)
		self.assertEqual(frappe.db.get_value("Leave Type", "Sick Leave", "include_holiday"), 0)
		self.assertEqual(
			frappe.db.get_value("Salary Component", "BPJS JHT Karyawan", "drea_finance_component"),
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
		employee = make_employee("drea.payroll.setup@example.com", company=COMPANY)
		setup.apply(dry_run=False, companies=[COMPANY])
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		structure = frappe.get_doc("Salary Structure", setup.STRUCTURE_NAME.format(abbr=abbr))
		if structure.docstatus == 0:
			structure.submit()

		from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
		from hrms.payroll.doctype.salary_structure.test_salary_structure import (
			create_salary_structure_assignment,
		)

		create_salary_structure_assignment(employee, structure.name, company=COMPANY, base=15_000_000)
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
		self.assertNotIn("PPh21", amounts)  # no formula yet, and a 0 line is removed
