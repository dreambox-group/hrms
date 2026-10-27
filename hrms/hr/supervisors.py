# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""An employee's supervisors: the people who approve their leave.

With HR Settings' "Approve Leave by Levels" these are the Required and Regular approvers of
get_leave_approvers; otherwise the employee's Leave Approver and their department's leave approvers,
any one of whom decides.
"""

import frappe
from frappe import _

from hrms.hr.doctype.leave_application.leave_application import (
	get_leave_approvers,
	is_leave_approval_by_levels,
)


def get_supervisors(employee: str) -> list[frappe._dict]:
	"""Rows of approver, approver_name, approval_level, department, decision ("Pending")."""
	if is_leave_approval_by_levels():
		return get_leave_approvers(employee)

	from hrms.api import leave_approval_details

	details = leave_approval_details(employee)
	department = frappe.db.get_value("Employee", employee, "department")
	return [
		frappe._dict(
			approver=row.get("name"),
			approver_name=row.get("full_name"),
			approval_level="Regular",
			department=department,
			decision="Pending",
		)
		for row in details["department_approvers"]
		if row.get("name")
	]


def get_supervisor_users(employee: str) -> set[str]:
	"""The supervisors' users; empty when none is set up (HR still sees everything)."""
	try:
		return {row.approver for row in get_supervisors(employee)}
	except frappe.ValidationError:
		return set()


# The other way round: a supervisor's team is everyone in the departments whose leave they approve
def get_supervised_departments(user: str) -> list[str]:
	return frappe.get_all(
		"Department Approver",
		filters={"parenttype": "Department", "parentfield": "leave_approvers", "approver": user},
		pluck="parent",
		distinct=True,
	)


def get_team(user: str) -> list[frappe._dict]:
	"""Active employees in the user's departments, without the user."""
	from hrms.hr.workforce_today import get_active_employees

	departments = get_supervised_departments(user)
	if not departments:
		return []
	return [e for e in get_active_employees(departments=departments) if e.user_id != user]


HR_ROLES = ("HR Manager", "HR User", "System Manager")


def get_viewable_employee(employee: str | None) -> str:
	"""The session employee, or someone whose details the user may see: their team member, or anyone for HR."""
	from hrms.api import get_current_employee

	if not employee:
		return get_current_employee()
	user = frappe.session.user
	if (
		frappe.db.get_value("Employee", employee, "user_id") == user
		or set(HR_ROLES) & set(frappe.get_roles(user))
		or employee in {member.name for member in get_team(user)}
	):
		return employee
	frappe.throw(_("You can only see your own team's attendance."), frappe.PermissionError)
