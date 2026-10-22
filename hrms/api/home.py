# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Data for the employee home page (/hr): today's notices, approvals waiting and the approver's team."""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, strip_html, today

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

from hrms.api import get_current_employee_info
from hrms.api.hr_dashboard import get_approval_progress
from hrms.hr.doctype.leave_application.leave_application import (
	get_leave_applications_waiting_for,
	is_leave_approval_by_levels,
)
from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label
from hrms.hr.doctype.leave_application.leave_documents import (
	get_leave_attachments,
	get_missing_documents_for,
)
from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift
from hrms.hr.workforce_today import (
	CHECKED_IN,
	HOLIDAY,
	LATE,
	ON_LEAVE,
	get_active_employees,
	get_celebrations,
	get_leave_on,
	get_workforce_today,
)


@frappe.whitelist()
def get_home_data() -> dict:
	user = frappe.session.user
	date = getdate(today())
	employee = get_current_employee_info() or {}
	company_employees = get_active_employees(employee.get("company")) if employee else []
	names = [e.name for e in company_employees]

	approvals = get_leave_approvals(user)
	team = get_team_today(user, date)
	return {
		"date": date,
		"on_leave_today": [
			{"employee_name": row.employee_name, "label": row.label, "to_date": row.to_date}
			for row in get_leave_on(names, date, date)
		],
		"birthdays_today": [
			c.employee_name for c in get_celebrations(company_employees, 1, date) if c.kind == "Birthday"
		],
		"leave_approvals": approvals,
		"other_approvals": get_other_approvals(user),
		"team": team,
		"approval_by_levels": is_leave_approval_by_levels(),
		"missing_documents": get_missing_documents_for(user),
		"me": get_my_day(employee, date) if employee else None,
		"next_holiday": get_next_holiday(employee.get("name"), date) if employee else None,
	}


def get_my_day(employee: dict, date) -> dict:
	"""The user's own status today, with the check-in times of their shift."""
	row = get_workforce_today([frappe._dict(employee)], date)[0]
	shift = get_employee_shift(employee["name"], datetime.combine(date, time(12)), True) or {}
	shift_type = shift.get("shift_type")
	row.opens_at = shift.get("actual_start")
	row.late_after = None
	if shift_type:
		# the shift details carry only some Shift Type fields
		late_marking, grace = frappe.get_cached_value(
			"Shift Type", shift_type.name, ["enable_late_entry_marking", "late_entry_grace_period"]
		)
		if cint(late_marking):
			row.late_after = shift["start_datetime"] + timedelta(minutes=cint(grace))
	row.leave_to_date = None
	if row.status == ON_LEAVE:
		leave = get_leave_on([employee["name"]], date, date)
		row.leave_to_date = leave[0].to_date if leave else None
	row.holiday = None
	if row.status == HOLIDAY:
		row.holiday = get_holiday_description(employee["name"], date)
	return row


def get_holiday_description(employee: str, date) -> str | None:
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return None
	description = frappe.db.get_value(
		"Holiday", {"parent": holiday_list, "holiday_date": date}, "description"
	)
	return strip_html(description or "").strip() or None


def get_next_holiday(employee: str, date) -> dict | None:
	"""The next public holiday (not a weekly day off) on the employee's holiday list."""
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return None
	holiday = frappe.db.get_value(
		"Holiday",
		{"parent": holiday_list, "holiday_date": (">=", date), "weekly_off": 0},
		["holiday_date", "description"],
		order_by="holiday_date",
		as_dict=True,
	)
	if holiday:
		holiday.description = strip_html(holiday.description or "").strip()
	return holiday


def get_leave_approvals(user: str) -> list[dict]:
	"""Open leave requests waiting for the user's decision, with where their approval stands."""
	if is_leave_approval_by_levels():
		names = get_leave_applications_waiting_for(user)
		filters = {"name": ("in", names or [""])}
	else:
		filters = {"leave_approver": user, "docstatus": 0, "status": "Open"}

	applications = frappe.get_all(
		"Leave Application",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"leave_type",
			"from_date",
			"to_date",
			"total_leave_days",
			"leave_approver_name",
			"description",
			"document_due_date",
		],
		order_by="from_date",
	)
	approvers = {}
	if applications:
		for row in frappe.get_all(
			"Leave Application Approver",
			filters={"parenttype": "Leave Application", "parent": ("in", [a.name for a in applications])},
			fields=["parent", "approver", "approver_name", "approval_level", "decision"],
			order_by="idx",
		):
			approvers.setdefault(row.parent, []).append(row)

	attachments = get_leave_attachments([a.name for a in applications])
	for application in applications:
		application.label = get_leave_label(application.employee, application.leave_type)
		application.approvers = approvers.get(application.name, [])
		application.progress = get_approval_progress(application)
		application.attachments = attachments.get(application.name, [])
		application.document_missing = bool(application.document_due_date and not application.attachments)
	return applications


def get_other_approvals(user: str) -> list[dict]:
	"""Counts of other requests where the user is the chosen approver."""
	return [
		{
			"doctype": "Expense Claim",
			"label": _("Expense claims"),
			"count": frappe.db.count(
				"Expense Claim", {"expense_approver": user, "docstatus": 0, "approval_status": "Draft"}
			),
		},
		{
			"doctype": "Shift Request",
			"label": _("Shift requests"),
			"count": frappe.db.count("Shift Request", {"approver": user, "docstatus": 0, "status": "Draft"}),
		},
	]


def get_team_today(user: str, date) -> dict | None:
	"""For leave approvers: who in their departments has checked in today."""
	departments = frappe.get_all(
		"Department Approver",
		filters={"parenttype": "Department", "parentfield": "leave_approvers", "approver": user},
		pluck="parent",
		distinct=True,
	)
	if not departments:
		return None

	employees = [e for e in get_active_employees(departments=departments) if e.user_id != user]
	rows = get_workforce_today(employees, date)
	return {
		"departments": sorted(departments),
		"total": len(rows),
		"checked_in": len([r for r in rows if r.status in (CHECKED_IN, LATE)]),
		"late": len([r for r in rows if r.status == LATE]),
		"rows": rows,
	}
