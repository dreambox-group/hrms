# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Drea payroll setup (hrms.payroll.drea_payroll_setup): components, their Drea Finance pay codes
and accounts, the retired components, the draft structure and the BPJS amounts on a real slip."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.payroll import drea_payroll_setup as setup
from hrms.payroll.drea_finance import ALLOWED_KINDS

COMPANY = "_Test Company"


class TestDreaPayrollSetup(IntegrationTestCase):
	def setUp(self):
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import TestPayrollEntry

		TestPayrollEntry.setUp(self)
		frappe.db.set_single_value("Payroll Settings", "email_salary_slip_to_employee", 0)

	def test_every_code_fits_its_component_type(self):
		for name, (_abbr, component_type, _formula, code, _days, _taxable) in setup.COMPONENTS.items():
			self.assertIn(setup.FINANCE_CODES[code][1], ALLOWED_KINDS[component_type], name)

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
			"THR",  # its own code, so Drea Finance's transfer list shows it apart
		)

	def test_drea_finance_codes_and_accounts(self):
		from hrms.drea_finance.doctype.drea_finance_settings.drea_finance_settings import mappings

		# an old per-partner mapping, from before the accounts table
		settings = frappe.get_single("Drea Finance Settings")
		settings.set("pay_codes", [r for r in settings.pay_codes if r.salary_component != "Incentive"])
		settings.append("pay_codes", {"salary_component": "Incentive", "pay_code": "PRIVE_SOMEONE"})
		settings.flags.ignore_validate = True
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)

		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		frappe.clear_document_cache("Drea Finance Settings", "Drea Finance Settings")
		codes = mappings()["codes"]
		self.assertEqual(
			codes["SALARY"], {"name": "Gaji", "kind": "earning", "account": "510201", "owed_account": None}
		)
		self.assertEqual(codes["PRIVE"]["account"], "310200")
		self.assertEqual(codes["THR"]["account"], "510202")
		self.assertEqual(
			(codes["BPJS_TK_COMPANY"]["account"], codes["BPJS_TK_COMPANY"]["owed_account"]),
			("510402", "210302"),
		)
		self.assertEqual(
			(codes["PPH21_COMPANY"]["account"], codes["PPH21_COMPANY"]["owed_account"]),
			("510521", "210421"),
		)
		# every mapped code is in the table; the per-partner PRIVE_<NAME> code is gone
		pay_codes = mappings()["pay_codes"]
		self.assertTrue(set(pay_codes.values()) <= set(codes))
		self.assertEqual(pay_codes["Prive"], "PRIVE")
		self.assertEqual(pay_codes["Incentive"], "INCENTIVE")
		# a second run finds nothing to do
		self.assertEqual(setup.apply(dry_run=True, companies=[COMPANY]), [])

	def test_leader_paid_by_prive(self):
		from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
		from hrms.payroll.doctype.salary_structure.test_salary_structure import (
			create_salary_structure_assignment,
		)

		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		employee = make_employee("drea.leader@example.com", company=COMPANY, date_of_joining="2025-01-01")
		abbr = frappe.get_cached_value("Company", COMPANY, "abbr")

		# one component and one structure for every partner, booked on the company's Prive account
		prive = frappe.get_doc("Salary Component", "Prive")
		self.assertEqual((prive.type, prive.is_tax_applicable), ("Earning", 0))
		account = next(row.account for row in prive.accounts if row.company == COMPANY)
		self.assertEqual(frappe.db.get_value("Account", account, "root_type"), "Equity")
		structure = frappe.get_doc("Salary Structure", f"Drea Leader - {abbr}")
		self.assertEqual([r.salary_component for r in structure.earnings], ["Prive"])
		self.assertEqual(structure.deductions + structure.employer_contributions, [])
		if structure.docstatus == 0:
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
		self.assertEqual(lines, {"Prive": 20_000_000})  # no BPJS, PPh 21 or cuts on a drawing
		self.assertEqual(slip.net_pay, 20_000_000)

	def test_pay_code_must_be_in_the_accounts_table(self):
		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		settings = frappe.get_single("Drea Finance Settings")
		settings.append("pay_codes", {"salary_component": "Incentive", "pay_code": "PRIVE_SOMEONE"})
		settings.flags.ignore_mandatory = True
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

	def test_pay_sheet_reading(self):
		from hrms.payroll.drea_pay_sheet import ptkp_from

		self.assertEqual(ptkp_from("Belum Menikah"), "TK/0")
		self.assertEqual(ptkp_from("Menikah, K/2"), "K/2")
		self.assertEqual(ptkp_from("Menikah"), "K/0")
		self.assertEqual(ptkp_from("TK/1"), "TK/1")
		self.assertIsNone(ptkp_from(""))
		self.assertIsNone(ptkp_from("Cerai"))
