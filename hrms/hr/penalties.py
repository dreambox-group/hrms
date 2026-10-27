# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""What will be deducted from an employee's pay this pay period, as counts of days.

HR: each late day is a fixed deduction, each day without a check-in is an unpaid day, and so is each
day of unpaid leave (leave types marked Leave Without Pay). The pay period runs from HR Settings' "Pay
Period Starts On Day" to the day before it next month (19 = 19 Sep–18 Oct).
"""

from datetime import datetime, time

import frappe
from frappe.utils import add_days, add_months, cint, getdate

from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days
from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift
from hrms.hr.workforce_today import get_leave_on, is_late


def get_pay_period(date=None) -> tuple:
	"""The first and last day of the pay period the date falls in."""
	date = getdate(date)
	start_day = min(max(cint(frappe.db.get_single_value("HR Settings", "pay_period_start_day")), 1), 28)
	start = date.replace(day=start_day)
	if date.day < start_day:
		start = add_months(start, -1)
	return start, add_days(add_months(start, 1), -1)


def get_penalties(employee: str, date=None) -> dict:
	from hrms.api.employee_app import get_attendance_days

	today = getdate(date)
	start, end = get_pay_period(today)
	leave = get_leave_on([employee], start, end)
	on_leave = {
		add_days(getdate(row.from_date), n)
		for row in leave
		for n in range((getdate(row.to_date) - getdate(row.from_date)).days + 1)
	}

	late, no_checkin = [], []
	for day in get_attendance_days(employee, start, min(end, today)):
		if day.status == "Absent":
			no_checkin.append(day.date)
		elif day.late_entry:
			late.append(day.date)
		elif day.status:
			continue
		elif day.checked_in_at:
			# no attendance marked yet: judged by the check-in, as on the Home page
			if is_late(day.checked_in_at, shift_on(employee, day.date)):
				late.append(day.date)
		# today still has time to check in
		elif day.date < today and not day.holiday and day.date not in on_leave and shift_on(employee, day.date):
			no_checkin.append(day.date)

	return {
		"period_start": start,
		"period_end": end,
		"late": late,
		"no_checkin": no_checkin,
		"unpaid_leave": get_unpaid_leave(employee, leave, start, end),
	}


def get_unpaid_leave(employee: str, leave: list[dict], start, end) -> list[dict]:
	"""Approved Leave Without Pay in the period, with its days counted inside the period."""
	unpaid_types = set(frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name"))
	rows = []
	for row in leave:
		if row.leave_type not in unpaid_types:
			continue
		half_day, half_day_date = frappe.db.get_value(
			"Leave Application", row.name, ["half_day", "half_day_date"]
		)
		from_date, to_date = max(getdate(row.from_date), start), min(getdate(row.to_date), end)
		if half_day and not (half_day_date and from_date <= getdate(half_day_date) <= to_date):
			half_day = 0
		days = get_number_of_leave_days(
			employee, row.leave_type, from_date, to_date, half_day, half_day_date, leave_application=row.name
		)
		if days:
			rows.append({"leave_type": row.leave_type, "from_date": from_date, "to_date": to_date, "days": days})
	return rows


def shift_on(employee: str, date) -> dict | None:
	shift = get_employee_shift(employee, datetime.combine(date, time(12)), True)
	return shift if shift and shift.get("shift_type") else None
