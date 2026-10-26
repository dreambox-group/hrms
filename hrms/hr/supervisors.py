# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""An employee's supervisors: the people who approve their leave.

With HR Settings' "Approve Leave by Levels" these are the Required and Regular approvers of
get_leave_approvers; otherwise the employee's Leave Approver and their department's leave approvers,
any one of whom decides.
"""

import frappe

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
