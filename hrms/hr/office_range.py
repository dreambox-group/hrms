# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Checking in outside the office.

An office shift's Shift Location has a check-in radius (at most 500 m). Further away the employee can
still check in, but picks a reason first (Meeting di Luar / Sudah izin Supervisor). That day their
supervisors (their leave approvers) see it on the employee app's Home page, and HR on the HR Dashboard.
"""

import frappe
from frappe.utils import cint, flt, getdate

from hrms.hr.supervisors import get_supervisor_users

OUTSIDE_OFFICE_REASONS = ("Meeting di Luar", "Sudah izin Supervisor")


def get_checkin_location(employee: str, shift: str | None, time) -> frappe._dict | None:
	"""The Shift Location of the employee's shift at the time, if it has a radius and coordinates."""
	if not shift:
		return None
	locations = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"shift_type": shift,
			"start_date": ["<=", getdate(time)],
			"shift_location": ["is", "set"],
			"docstatus": 1,
			"status": "Active",
		},
		or_filters=[["end_date", ">=", getdate(time)], ["end_date", "is", "not set"]],
		pluck="shift_location",
		order_by="start_date desc",
		limit=1,
	)
	if not locations:
		return None

	location = frappe.db.get_value(
		"Shift Location", locations[0], ["name", "checkin_radius", "latitude", "longitude"], as_dict=True
	)
	# no radius = no check (working from home); no coordinates = the office isn't set up yet
	if not location or cint(location.checkin_radius) <= 0 or not (flt(location.latitude) or flt(location.longitude)):
		return None
	location.radius = cint(location.checkin_radius)
	return location


def get_outside_office_checkins(date, employees: list[str] | None = None, company: str | None = None) -> list[dict]:
	"""Each employee's first check-in outside the office range on the date."""
	filters = {
		"outside_office_range": 1,
		"time": ["between", [f"{getdate(date)} 00:00:00", f"{getdate(date)} 23:59:59"]],
	}
	if employees is not None:
		if not employees:
			return []
		filters["employee"] = ("in", employees)
	rows = frappe.get_all(
		"Employee Checkin",
		filters=filters,
		fields=["name", "employee", "employee_name", "time", "office_distance", "outside_office_reason", "shift"],
		order_by="time",
	)
	if company:
		in_company = set(
			frappe.get_all(
				"Employee",
				filters={"name": ("in", [r.employee for r in rows] or [""]), "company": company},
				pluck="name",
			)
		)
		rows = [r for r in rows if r.employee in in_company]

	first = {}
	for row in rows:
		first.setdefault(row.employee, row)
	departments = dict(
		frappe.get_all(
			"Employee", filters={"name": ("in", list(first) or [""])}, fields=["name", "department"], as_list=True
		)
	)
	for row in first.values():
		row.department = departments.get(row.employee)
		row.location = get_checkin_location(row.employee, row.shift, row.time)
		row.location = row.location.name if row.location else None
	return list(first.values())


def get_outside_office_for_supervisor(user: str, date) -> list[dict]:
	"""Today's check-ins outside the office by employees whose supervisor (leave approver) the user is."""
	return [row for row in get_outside_office_checkins(date) if user in get_supervisor_users(row.employee)]
