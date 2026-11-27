# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Drea payroll, 27 Nov 2026: the pay calendar (19th to 18th, paid the 27th), the unpaid-days line,
PPh 21 paid by the company (TER, the year's sum in December) and the THR drafts."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.payroll import drea_pay_calendar, drea_pph21, drea_thr
from hrms.payroll import drea_payroll_setup as setup
from hrms.payroll.doctype.payroll_entry.payroll_entry import get_start_end_dates

COMPANY = "_Test Company"


class TestPPh21Sums(IntegrationTestCase):
	def test_ter_rates_at_their_edges(self):
		self.assertEqual(drea_pph21.ter_rate("A", 5_400_000), 0)
		self.assertEqual(drea_pph21.ter_rate("A", 5_400_001), 0.25)
		self.assertEqual(drea_pph21.ter_rate("B", 6_200_000), 0)
		self.assertEqual(drea_pph21.ter_rate("C", 9_000_000), 1.25)
		self.assertEqual(drea_pph21.ter_rate("A", 1_400_000_001), 34)
		self.assertEqual(len(drea_pph21.TER["A"]), 43)  # 44 rows with the top one
		self.assertEqual(len(drea_pph21.TER["B"]), 39)
		self.assertEqual(len(drea_pph21.TER["C"]), 40)
		for rows in drea_pph21.TER.values():
			tops = [top for top, _rate in rows]
			rates = [rate for _top, rate in rows]
			self.assertEqual(tops, sorted(tops))
			self.assertEqual(rates, sorted(rates))

	def test_ter_tax_rounds_down(self):
		self.assertEqual(drea_pph21.ter_tax("A", 10_200_000), 229_500)  # 2.25%
		self.assertEqual(drea_pph21.ter_tax("A", 5_500_003), 13_750)  # 0.25%, rounded down

	def test_every_ptkp_status_has_a_category(self):
		self.assertEqual(set(drea_pph21.PTKP), set(drea_pph21.CATEGORY))

	def test_pasal_17_bands(self):
		self.assertEqual(drea_pph21.pasal_17(0), 0)
		self.assertEqual(drea_pph21.pasal_17(60_000_000), 3_000_000)
		self.assertEqual(drea_pph21.pasal_17(100_000_000), 3_000_000 + 6_000_000)
		self.assertEqual(drea_pph21.pasal_17(600_000_000), 3_000_000 + 28_500_000 + 62_500_000 + 30_000_000)

	def test_the_years_tax(self):
		# 12 x Rp15,561,000 gross; job costs capped at Rp6,000,000; JHT and JP 12 x Rp405,474
		year = drea_pph21.year_tax(186_732_000, 4_865_688, 12, drea_pph21.PTKP["TK/0"])
		self.assertEqual(year.job_cost, 6_000_000)
		self.assertEqual(year.net, 175_866_312)
		self.assertEqual(year.taxable, 121_866_000)
		self.assertEqual(year.tax, 3_000_000 + 9_279_900)  # 5% of 60M, 15% of 61,866,000


class TestPayCalendar(IntegrationTestCase):
	def setUp(self):
		frappe.db.set_single_value("HR Settings", {"pay_period_start_day": 19, "pay_day": 27})

	def test_period_a_date_falls_in(self):
		found = drea_pay_calendar.period("2026-11-05")
		self.assertEqual((str(found.start_date), str(found.end_date)), ("2026-10-19", "2026-11-18"))
		found = drea_pay_calendar.period("2026-11-19")
		self.assertEqual((str(found.start_date), str(found.end_date)), ("2026-11-19", "2026-12-18"))

	def test_period_to_pay_next(self):
		for today, start, end, pay in (
			("2026-11-25", "2026-10-19", "2026-11-18", "2026-11-27"),
			("2026-11-27", "2026-10-19", "2026-11-18", "2026-11-27"),
			("2026-11-28", "2026-11-19", "2026-12-18", "2026-12-27"),
			("2026-12-27", "2026-11-19", "2026-12-18", "2026-12-27"),
			("2027-01-02", "2026-12-19", "2027-01-18", "2027-01-27"),
		):
			found = get_start_end_dates("Monthly", today, to_pay=1)
			self.assertEqual(
				(str(found.start_date), str(found.end_date), str(found.pay_date)), (start, end, pay), today
			)

	def test_off_is_the_calendar_month(self):
		frappe.db.set_single_value("HR Settings", {"pay_period_start_day": 1, "pay_day": 0})
		self.assertIsNone(drea_pay_calendar.period("2026-11-05"))
		found = get_start_end_dates("Monthly", "2026-11-05", COMPANY)
		self.assertEqual((str(found.start_date), str(found.end_date)), ("2026-11-01", "2026-11-30"))


class TestPayrollOnSlips(IntegrationTestCase):
	def setUp(self):
		from hrms.payroll.doctype.payroll_entry.test_payroll_entry import TestPayrollEntry

		TestPayrollEntry.setUp(self)
		frappe.db.set_single_value(
			"Payroll Settings",
			{
				"email_salary_slip_to_employee": 0,
				"payroll_based_on": "Attendance",
				"consider_unmarked_attendance_as": "Present",
				"include_holidays_in_total_working_days": 0,
				"calculate_pph21": 1,
			},
		)
		setup.apply(dry_run=False, companies=[COMPANY], commit=False)
		self.abbr = frappe.get_cached_value("Company", COMPANY, "abbr")
		for kind in ("Full-time", "Intern"):
			structure = frappe.get_doc("Salary Structure", f"Drea {kind} - {self.abbr}")
			if structure.docstatus == 0:
				structure.submit()

	def slip(self, user, base, posting_date, status="TK/0", kind="Full-time"):
		from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
		from hrms.payroll.doctype.salary_structure.test_salary_structure import (
			create_salary_structure_assignment,
		)

		employee = make_employee(user, company=COMPANY, date_of_joining="2025-01-01")
		frappe.db.set_value("Employee", employee, "ptkp_status", status)
		structure = f"Drea {kind} - {self.abbr}"
		create_salary_structure_assignment(
			employee, structure, company=COMPANY, base=base, from_date="2025-01-01"
		)
		return employee, make_salary_slip(structure, employee=employee, posting_date=posting_date)

	def lines(self, slip):
		return {
			row.salary_component: row.amount
			for table in ("earnings", "deductions", "employer_contributions")
			for row in slip.get(table)
		}

	def test_pph21_is_paid_by_the_company(self):
		_employee, slip = self.slip("drea.pph21.ter@example.com", 15_000_000, "2026-11-25")
		self.assertEqual((str(slip.start_date), str(slip.end_date)), ("2026-10-19", "2026-11-18"))
		lines = self.lines(slip)
		# gross for TER: 15,000,000 + BPJS Kesehatan 480,000 + JKK 36,000 + JKM 45,000 = 15,561,000: 7%
		self.assertEqual(lines["PPh21"], 1_089_270)
		self.assertIn("PPh21", [r.salary_component for r in slip.employer_contributions])
		self.assertNotIn("PPh21", [r.salary_component for r in slip.deductions])
		# take-home is not touched by PPh 21
		self.assertEqual(slip.net_pay, 15_000_000 - 120_000 - 300_000 - round(setup.JP_WAGE_CAP * 0.01))
		self.assertIn("TER A (TK/0)", slip.pph21_working)

	def test_unpaid_day_is_its_own_line(self):
		employee, slip = self.slip("drea.pph21.unpaid@example.com", 15_000_000, "2026-11-25")
		day = next(
			d
			for d in (frappe.utils.add_days(slip.start_date, i) for i in range(30))
			if d not in slip.get_holidays_for_employee(slip.start_date, slip.end_date)
		)
		frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": employee,
				"attendance_date": day,
				"status": "Absent",
				"company": COMPANY,
			}
		).submit()
		slip.get_emp_and_working_day_details()
		slip.calculate_net_pay()
		lines = self.lines(slip)
		self.assertEqual(slip.absent_days, 1)
		self.assertEqual(lines["Basic"], 15_000_000)  # the full base stays on the slip
		self.assertEqual(lines["Unpaid Leave"], round(15_000_000 / slip.total_working_days))
		# PPh 21 is worked out on what was earned, after the cut
		gross = 15_000_000 - lines["Unpaid Leave"] + 480_000 + 36_000 + 45_000
		self.assertEqual(lines["PPh21"], drea_pph21.ter_tax("A", gross))

	def test_december_works_out_the_whole_year(self):
		_employee, slip = self.slip("drea.pph21.dec@example.com", 15_000_000, "2026-12-27")
		self.assertEqual(str(slip.end_date), "2026-12-18")
		# one month on payroll this year: net 14,655,526 is under PTKP, so nothing is due
		self.assertNotIn("PPh21", self.lines(slip))
		self.assertIn("Year's last month (1 months)", slip.pph21_working)

	def test_interns_have_no_bpjs(self):
		_employee, slip = self.slip("drea.pph21.intern@example.com", 3_000_000, "2026-11-25", kind="Intern")
		lines = self.lines(slip)
		self.assertEqual(lines, {"Basic": 3_000_000})  # TER A is 0% up to 5,400,000
		self.assertEqual(slip.net_pay, 3_000_000)

	def test_needs_a_ptkp_status(self):
		with self.assertRaises(frappe.ValidationError):
			self.slip("drea.pph21.noptkp@example.com", 15_000_000, "2026-11-25", status="")

	def test_off_leaves_pph21_out(self):
		frappe.db.set_single_value("Payroll Settings", "calculate_pph21", 0)
		_employee, slip = self.slip("drea.pph21.off@example.com", 15_000_000, "2026-11-25")
		self.assertNotIn("PPh21", self.lines(slip))
		self.assertFalse(slip.get("pph21_working"))

	def test_thr_drafts(self):
		self.assertEqual(drea_thr.months_served("2026-01-15", "2027-03-10"), 13)
		self.assertEqual(drea_thr.months_served("2026-06-11", "2027-03-10"), 8)
		self.assertEqual(drea_thr.thr_amount(12_000_000, 8), 8_000_000)
		self.assertEqual(drea_thr.thr_amount(12_000_000, 0), 0)

		staff, _slip = self.slip("drea.thr.staff@example.com", 12_000_000, "2026-11-25")
		intern, _slip = self.slip("drea.thr.intern@example.com", 3_000_000, "2026-11-25", kind="Intern")
		result = drea_thr.draft_thr(COMPANY, "2027-03-10", "2027-03-01")
		drafts = frappe.get_all(
			"Additional Salary",
			filters={"salary_component": "THR", "docstatus": 0, "payroll_date": "2027-03-01"},
			fields=["employee", "amount"],
		)
		self.assertIn({"employee": staff, "amount": 12_000_000}, [dict(d) for d in drafts])
		self.assertNotIn(intern, [d.employee for d in drafts])
		self.assertTrue(result["made"])
		# a second go makes nothing new
		again = drea_thr.draft_thr(COMPANY, "2027-03-10", "2027-03-01")
		self.assertFalse(
			[
				m
				for m in again["made"]
				if m.startswith(frappe.db.get_value("Employee", staff, "employee_name"))
			]
		)
