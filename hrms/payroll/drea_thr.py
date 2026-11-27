# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""THR drafts (owner, 27 Nov 2026). Frappe HR has no THR feature of its own; its standard way to
pay a one-off amount is an Additional Salary, which the payroll run of that month picks up. This
only works out the amounts and makes the drafts (Additional Salary list > Draft THR); HR checks
them and submits them as usual.

The amount (Permenaker 6/2016): a month's wage after 12 months' service by Hari Raya, otherwise
months served / 12 of it, from one full month. The wage is the base in the person's Salary
Structure Assignment (Drea pays no fixed allowances; owner, 27 Nov 2026). Only staff on a
"Drea Full-time" structure: interns and freelancers are not employees under the labour law.
THR is part of that month's gross for PPh 21 (hrms.payroll.drea_pph21) and goes to Drea Finance
as INCENTIVE.
"""

from dateutil.relativedelta import relativedelta

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, get_first_day, get_last_day, getdate

THR = "THR"
STRUCTURE_PREFIX = "Drea Full-time - "


def months_served(joined, holiday) -> int:
	served = relativedelta(getdate(holiday), getdate(joined))
	return served.years * 12 + served.months


def thr_amount(base, months: int) -> int:
	if months < 1:
		return 0
	if months >= 12:
		return round(flt(base))
	return round(flt(base) * months / 12)


@frappe.whitelist()
def draft_thr(company: str, holiday_date: str, payroll_date: str) -> dict:
	"""Make a draft THR Additional Salary for everyone due one. Returns what was made and skipped."""
	frappe.only_for(["HR Manager", "HR User", "System Manager"])
	holiday, payroll = getdate(holiday_date), getdate(payroll_date)
	if payroll > holiday:
		frappe.throw(
			_("THR must be paid before Hari Raya: choose a payroll date on or before {0}.").format(holiday)
		)

	made, skipped = [], []
	employees = frappe.get_all(
		"Employee",
		filters={"company": company, "status": "Active", "date_of_joining": ("<=", holiday)},
		fields=["name", "employee_name", "date_of_joining"],
		order_by="employee_name",
	)
	for emp in employees:
		ssa = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": emp.name, "docstatus": 1, "from_date": ("<=", payroll)},
			fields=["salary_structure", "base", "currency"],
			order_by="from_date desc",
			limit=1,
		)
		if not ssa or not ssa[0].salary_structure.startswith(STRUCTURE_PREFIX):
			continue  # not full-time staff on payroll
		months = months_served(emp.date_of_joining, holiday)
		amount = thr_amount(ssa[0].base, months)
		if not amount:
			skipped.append(_("{0}: less than a month's service by Hari Raya").format(emp.employee_name))
			continue
		if frappe.db.exists(
			"Additional Salary",
			{
				"employee": emp.name,
				"salary_component": THR,
				"docstatus": ("<", 2),
				"payroll_date": ("between", [get_first_day(payroll), get_last_day(payroll)]),
			},
		):
			skipped.append(_("{0}: already has THR this month").format(emp.employee_name))
			continue
		frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": emp.name,
				"company": company,
				"salary_component": THR,
				"amount": amount,
				"payroll_date": payroll,
				"currency": ssa[0].currency,
				"overwrite_salary_structure_amount": 1,
			}
		).insert()
		made.append(
			_("{0}: {1} ({2})").format(
				emp.employee_name,
				fmt_money(amount, currency=ssa[0].currency),
				_("12 months or more") if months >= 12 else _("{0} of 12 months").format(months),
			)
		)
	return {"made": made, "skipped": skipped}
