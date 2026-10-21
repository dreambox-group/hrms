# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import frappe
from frappe.utils import add_days, get_first_day, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.attendance.attendance import mark_attendance
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
from hrms.payroll.doctype.salary_structure.test_salary_structure import make_salary_structure
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
PENALTY = "_Test Late Penalty"


class TestSalarySlipLateDays(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Salary Component", PENALTY):
			frappe.get_doc(
				{
					"doctype": "Salary Component",
					"salary_component": PENALTY,
					"salary_component_abbr": "TLP",
					"type": "Deduction",
					"depends_on_payment_days": 0,
				}
			).insert()

	def test_late_days_are_counted_and_deducted(self):
		employee = make_employee("late.penalty@example.com", COMPANY)
		month_start = get_first_day(getdate())
		frappe.db.delete("Attendance", {"employee": employee})
		mark_attendance(employee, month_start, "Present", late_entry=True)
		mark_attendance(employee, add_days(month_start, 1), "Present", late_entry=True)
		mark_attendance(employee, add_days(month_start, 2), "Present")
		# last month's late day doesn't count
		mark_attendance(employee, add_days(month_start, -1), "Present", late_entry=True)

		structure = make_salary_structure(
			"_Test Late Penalty Structure",
			"Monthly",
			employee=employee,
			company=COMPANY,
			from_date=add_days(month_start, -40),
			deductions=[
				{
					"salary_component": PENALTY,
					"abbr": "TLP",
					"amount_based_on_formula": 1,
					"formula": "late_entry_days * 50000",
				}
			],
		)
		slip = make_salary_slip(structure.name, employee=employee, posting_date=month_start)
		slip.insert()

		self.assertEqual(slip.late_entry_days, 2)
		penalty = next(d for d in slip.deductions if d.salary_component == PENALTY)
		self.assertEqual(penalty.amount, 100000)
