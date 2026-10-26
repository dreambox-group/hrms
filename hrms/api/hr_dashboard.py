# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Data for the HR Dashboard desk page (/desk/hr-dashboard): one call for every widget."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label
from hrms.hr.doctype.leave_application.leave_documents import get_missing_documents
from hrms.hr.office_range import get_outside_office_checkins
from hrms.hr.workforce_today import (
	CHECKED_IN,
	LATE,
	NOT_IN,
	ON_LEAVE,
	get_active_employees,
	get_celebrations,
	get_leave_on,
	get_shift_locations,
	get_workforce_today,
)

HR_ROLES = ("HR Manager", "HR User", "System Manager")
RECENT_DAYS = 14
UPCOMING_DAYS = 30


@frappe.whitelist()
def get_dashboard_data(company: str | None = None) -> dict:
	if not set(HR_ROLES) & set(frappe.get_roles()):
		frappe.throw(_("The HR Dashboard is for HR users."), frappe.PermissionError)

	date = getdate(today())
	employees = get_active_employees(company or None)
	names = [e.name for e in employees]
	workforce = get_workforce_today(employees, date)
	counts = Counter(row.status for row in workforce)
	week_start = add_days(date, -date.weekday())
	celebrations = get_celebrations(employees, 7, date)
	leave = get_leave_requests(company)

	return {
		"date": date,
		"companies": frappe.get_all("Company", pluck="name", order_by="name"),
		"stats": {
			"active_employees": len(employees),
			"checked_in": counts[CHECKED_IN] + counts[LATE],
			"on_leave": counts[ON_LEAVE],
			"leave_waiting": len(leave["waiting"]),
			"celebrations_this_week": len(celebrations),
		},
		"attendance": {
			"counts": {status: counts[status] for status in (CHECKED_IN, LATE, NOT_IN, ON_LEAVE)},
			"not_in": [row for row in workforce if row.status == NOT_IN],
		},
		"leave": leave,
		"away": {
			"today": get_leave_on(names, date, date),
			"week": get_leave_on(names, week_start, add_days(week_start, 6)),
		},
		"celebrations": celebrations,
		"shifts": get_shifts_today(workforce, date),
		"headcount": get_headcount(employees),
		"changes": get_people_changes(company, date),
		"requests": get_other_requests(company),
		"missing_documents": get_missing_documents({"company": company} if company else None),
		"outside_office": get_outside_office_checkins(date, company=company or None),
	}


def get_leave_requests(company: str | None) -> dict:
	filters = {"company": company} if company else {}
	fields = [
		"name",
		"employee",
		"employee_name",
		"leave_type",
		"from_date",
		"to_date",
		"total_leave_days",
		"leave_approver_name",
		"modified",
	]
	recent = add_days(today(), -RECENT_DAYS)
	requests = {
		"waiting": frappe.get_all(
			"Leave Application",
			filters={**filters, "docstatus": 0, "status": "Open"},
			fields=fields,
			order_by="from_date",
		),
		"approved": frappe.get_all(
			"Leave Application",
			filters={**filters, "docstatus": 1, "status": "Approved", "modified": (">=", recent)},
			fields=fields,
			order_by="modified desc",
		),
		"rejected": frappe.get_all(
			"Leave Application",
			filters={**filters, "docstatus": 1, "status": "Rejected", "modified": (">=", recent)},
			fields=fields,
			order_by="modified desc",
		),
	}

	all_names = [row.name for rows in requests.values() for row in rows]
	approvers = {}
	if all_names:
		for row in frappe.get_all(
			"Leave Application Approver",
			filters={"parenttype": "Leave Application", "parent": ("in", all_names)},
			fields=["parent", "approver", "approver_name", "approval_level", "decision"],
			order_by="idx",
		):
			approvers.setdefault(row.parent, []).append(row)

	for rows in requests.values():
		for row in rows:
			row.label = get_leave_label(row.employee, row.leave_type)
			row.approvers = approvers.get(row.name, [])
			row.progress = get_approval_progress(row)
	return requests


def get_approval_progress(application) -> list[str]:
	"""Short lines on where the approval stands, e.g. ["Required 1 of 2 approved", "Regular: waiting"]."""
	if not application.approvers:
		return (
			[_("Approver: {0}").format(application.leave_approver_name)]
			if application.leave_approver_name
			else []
		)

	required = [a for a in application.approvers if a.approval_level == "Required"]
	regular = [a for a in application.approvers if a.approval_level == "Regular"]
	lines = [
		_("Required {0} of {1} approved").format(
			len([a for a in required if a.decision == "Approved"]), len(required)
		)
	]
	if not regular:
		lines.append(_("No Regular approver"))
	elif decided := next((a for a in regular if a.decision != "Pending"), None):
		lines.append(
			_("Regular: {0} by {1}").format(
				_(decided.decision).lower(), decided.approver_name or decided.approver
			)
		)
	else:
		lines.append(_("Regular: waiting"))

	rejected_by = [a.approver_name or a.approver for a in application.approvers if a.decision == "Rejected"]
	if rejected_by:
		lines = [_("Rejected by {0}").format(", ".join(rejected_by))]
	return lines


def get_shifts_today(workforce: list[dict], date) -> list[dict]:
	locations = get_shift_locations([row.employee for row in workforce if row.shift], date)
	shifts = {}
	for row in workforce:
		if not row.shift:
			continue
		shift = shifts.setdefault(
			row.shift,
			frappe._dict(
				name=row.shift,
				start=row.shift_start,
				end=row.shift_end,
				people=0,
				locations=set(),
			),
		)
		shift.people += 1
		if location := locations.get(row.employee):
			shift.locations.add(location)

	for shift in shifts.values():
		shift.locations = sorted(shift.locations)
	return sorted(shifts.values(), key=lambda s: (s.start, s.name))


def get_headcount(employees: list[dict]) -> list[dict]:
	counts = Counter(e.department or _("No department") for e in employees)
	return [{"department": department, "count": count} for department, count in counts.most_common()]


def get_people_changes(company: str | None, date) -> list[dict]:
	"""Joining, leaving, contracts and probation ending in the next 30 days."""
	until = add_days(date, UPCOMING_DAYS)
	filters = {"company": company} if company else {}
	fields = ["name", "employee_name", "department", "employment_type"]
	changes = []

	def add(field, status, kind):
		for row in frappe.get_all(
			"Employee",
			filters={**filters, "status": status, field: ("between", [date, until])},
			fields=[*fields, field],
		):
			row.kind = kind(row) if callable(kind) else kind
			row.date = row[field]
			changes.append(row)

	add("date_of_joining", "Active", "Joins")
	add("relieving_date", ("in", ["Active", "Left"]), "Leaves")
	add(
		"contract_end_date",
		"Active",
		lambda r: "Internship ends" if r.employment_type == "Intern" else "Contract ends",
	)
	add("final_confirmation_date", "Active", "Probation ends")
	return sorted(changes, key=lambda c: (c.date, c.employee_name))


def get_other_requests(company: str | None) -> list[dict]:
	filters = {"company": company} if company else {}
	return [
		{
			"doctype": "Expense Claim",
			"label": _("Expense claims"),
			"count": frappe.db.count(
				"Expense Claim", {**filters, "docstatus": 0, "approval_status": "Draft"}
			),
		},
		{
			"doctype": "Attendance Request",
			"label": _("Attendance requests"),
			"count": frappe.db.count("Attendance Request", {**filters, "docstatus": 0}),
		},
		{
			"doctype": "Shift Request",
			"label": _("Shift requests"),
			"count": frappe.db.count("Shift Request", {**filters, "docstatus": 0, "status": "Draft"}),
		},
		{
			"doctype": "Employee Advance",
			"label": _("Employee advances"),
			"count": frappe.db.count("Employee Advance", {**filters, "docstatus": 0}),
		},
	]
