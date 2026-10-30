# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Where everyone is today, for the HR Dashboard and the leave approvers' "team today" view."""

from datetime import datetime, time, timedelta

import frappe
from frappe.query_builder.functions import Min
from frappe.utils import add_days, cint, getdate

from erpnext.setup.doctype.employee.employee import is_holiday

from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label
from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift

CHECKED_IN = "Checked in"
LATE = "Late"
NOT_IN = "Not checked in"
ON_LEAVE = "On leave"
HOLIDAY = "Holiday"
NO_SHIFT = "No shift"


def get_active_employees(company: str | None = None, departments: list[str] | None = None) -> list[dict]:
	filters = {"status": "Active"}
	if company:
		filters["company"] = company
	if departments is not None:
		filters["department"] = ("in", departments or [""])
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"department",
			"company",
			"user_id",
			"image",
			"employment_type",
			"date_of_birth",
			"date_of_joining",
		],
		order_by="employee_name",
	)


def get_leave_on(employees: list[str], from_date, to_date) -> list[dict]:
	"""Approved leave of these employees overlapping the dates."""
	if not employees:
		return []
	leave = frappe.get_all(
		"Leave Application",
		filters={
			"employee": ("in", employees),
			"docstatus": 1,
			"status": "Approved",
			"from_date": ("<=", to_date),
			"to_date": (">=", from_date),
		},
		fields=["name", "employee", "employee_name", "department", "leave_type", "from_date", "to_date"],
		order_by="from_date, employee_name",
	)
	for row in leave:
		row.label = get_leave_label(row.employee, row.leave_type)
	return leave


def get_workforce_today(employees: list[dict], date=None) -> list[dict]:
	"""Each employee's status today: checked in, late, not yet in, on leave, holiday or no shift."""
	date = getdate(date)
	names = [e.name for e in employees]
	if not names:
		return []

	on_leave = {row.employee: row for row in get_leave_on(names, date, date)}
	Checkin = frappe.qb.DocType("Employee Checkin")
	first_in = dict(
		frappe.qb.from_(Checkin)
		.select(Checkin.employee, Min(Checkin.time))
		.where(
			Checkin.employee.isin(names)
			& Checkin.time[datetime.combine(date, time.min) : datetime.combine(date, time.max)]
			& (Checkin.log_type.isnull() | (Checkin.log_type != "OUT"))
		)
		.groupby(Checkin.employee)
		.run()
	)

	rows = []
	for employee in employees:
		shift = get_employee_shift(employee.name, datetime.combine(date, time(12)), True) or {}
		shift_type = shift.get("shift_type")
		row = frappe._dict(
			employee=employee.name,
			employee_name=employee.employee_name,
			department=employee.department,
			image=employee.image,
			shift=shift_type.name if shift_type else None,
			shift_start=shift.get("start_datetime"),
			shift_end=shift.get("end_datetime"),
			checked_in_at=first_in.get(employee.name),
			leave_label=None,
		)

		# a holiday inside a leave is still a holiday, not a leave day
		if employee.name in on_leave and not is_holiday(employee.name, date, raise_exception=False):
			row.status = ON_LEAVE
			row.leave_label = on_leave[employee.name].label
		elif row.checked_in_at:
			row.status = LATE if is_late(row.checked_in_at, shift) else CHECKED_IN
		elif is_holiday(employee.name, date, raise_exception=False):
			row.status = HOLIDAY
		elif not shift_type:
			row.status = NO_SHIFT
		else:
			row.status = NOT_IN
		rows.append(row)

	return rows


def is_late(checked_in_at, shift: dict) -> bool:
	if not shift or not shift.get("start_datetime"):
		return False
	grace = 0
	late_marking = frappe.get_cached_value(
		"Shift Type", shift["shift_type"].name, ["enable_late_entry_marking", "late_entry_grace_period"]
	)
	if late_marking and cint(late_marking[0]):
		grace = cint(late_marking[1])
	return checked_in_at > shift["start_datetime"] + timedelta(minutes=grace)


def get_shift_locations(employees: list[str], date=None) -> dict[str, str]:
	"""Shift Location of each employee's active shift assignment on the date."""
	date = getdate(date)
	if not employees:
		return {}
	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": ("in", employees),
			"docstatus": 1,
			"status": "Active",
			"start_date": ("<=", date),
			"shift_location": ("is", "set"),
		},
		or_filters=[["end_date", ">=", date], ["end_date", "=", None]],
		fields=["employee", "shift_location"],
	)
	return {row.employee: row.shift_location for row in assignments}


def get_celebrations(employees: list[dict], days: int = 7, date=None) -> list[dict]:
	"""Birthdays and work anniversaries (1 year or more) from the date for the next `days` days."""
	date = getdate(date)
	upcoming = {add_days(date, i).strftime("%m-%d"): add_days(date, i) for i in range(days)}
	celebrations = []
	for employee in employees:
		if employee.date_of_birth and (when := upcoming.get(employee.date_of_birth.strftime("%m-%d"))):
			celebrations.append(
				frappe._dict(
					employee=employee.name, employee_name=employee.employee_name, kind="Birthday", date=when
				)
			)
		if employee.date_of_joining and (when := upcoming.get(employee.date_of_joining.strftime("%m-%d"))):
			years = when.year - employee.date_of_joining.year
			if years >= 1:
				celebrations.append(
					frappe._dict(
						employee=employee.name,
						employee_name=employee.employee_name,
						kind="Work anniversary",
						years=years,
						date=when,
					)
				)
	return sorted(celebrations, key=lambda c: (c.date, c.employee_name))
