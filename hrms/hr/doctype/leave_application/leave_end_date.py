# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Leave pushes the end date, for "Employee Types without Leave Allocation" (HR Settings).

Employees whose Employment Type is in that list get no leave allocation; each approved leave day
moves their Contract End Date one working day later (holidays of their holiday list skipped, the
total rounded up), and cancelling the leave moves it back.

The end date is always recalculated from two Employee fields, so cancellations and half days can
never leave it wrong: Original Contract End Date + the approved leave starting on or after Leave
Counted From. Editing Contract End Date by hand (a renewal) restarts both.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_days, flt, formatdate, getdate, today

from hrms.utils.holiday_list import get_holiday_dates_between_range

SETTINGS_FIELD = "employment_types_without_leave_allocation"
HR_ROLES = ("HR Manager", "HR User", "System Manager")
TRACKED_FIELDS = ("original_contract_end_date", "leave_counted_from")


def get_types_without_allocation() -> set[str]:
	return set(
		frappe.get_all(
			"HR Settings Employment Type",
			filters={"parenttype": "HR Settings", "parentfield": SETTINGS_FIELD},
			pluck="employment_type",
		)
	)


def uses_leave_end_date(employee: str, employment_type: str | None = None) -> bool:
	if employment_type is None:
		employment_type = frappe.db.get_value("Employee", employee, "employment_type")
	return bool(employment_type) and employment_type in get_types_without_allocation()


def counted_leave_days(employee: str, counted_from, extra: float = 0) -> int:
	"""Approved leave starting on or after the date, plus `extra`, rounded up to whole days."""
	taken = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": (">=", getdate(counted_from)),
		},
		pluck="total_leave_days",
	)
	return math.ceil(sum(flt(days) for days in taken) + flt(extra))


def add_working_days(employee: str, start, days: int):
	"""The date `days` working days after `start`, skipping the employee's holidays."""
	start = getdate(start)
	if days <= 0:
		return start
	# a generous window; holidays rarely take more than twice the span plus a month
	window_end = add_days(start, days * 3 + 45)
	holidays = {
		getdate(d)
		for d in get_holiday_dates_between_range(
			employee, add_days(start, 1), window_end, raise_exception_for_holiday_list=False
		)
	}
	date, left = start, days
	while left > 0:
		date = add_days(date, 1)
		if date not in holidays:
			left -= 1
	return date


def end_date_details(employee: str, extra: float = 0) -> dict | None:
	"""Where the employee's end date stands, and where it would be with `extra` more leave days."""
	if not uses_leave_end_date(employee):
		return None
	row = frappe.db.get_value(
		"Employee",
		employee,
		["contract_end_date", "original_contract_end_date", "leave_counted_from"],
		as_dict=True,
	)
	original = row.original_contract_end_date or row.contract_end_date
	details = frappe._dict(
		applies=1, contract_end_date=row.contract_end_date, original_contract_end_date=original
	)
	if not original:
		return details
	counted_from = row.leave_counted_from or getdate(today())
	details.leave_counted_from = counted_from
	details.days_moved = counted_leave_days(employee, counted_from)
	if extra:
		details.end_date_after = add_working_days(
			employee, original, counted_leave_days(employee, counted_from, extra)
		)
	return details


def recalculate_end_date(employee: str, reference: str | None = None) -> None:
	"""Sets Contract End Date from the original date and the approved leave since Leave Counted From."""
	if not uses_leave_end_date(employee):
		return
	row = frappe.db.get_value(
		"Employee",
		employee,
		["contract_end_date", "original_contract_end_date", "leave_counted_from"],
		as_dict=True,
	)
	original = row.original_contract_end_date or row.contract_end_date
	if not original:
		return  # nothing to move

	updates = {}
	if not row.original_contract_end_date:
		updates["original_contract_end_date"] = original
	counted_from = row.leave_counted_from
	if not counted_from:
		counted_from = updates["leave_counted_from"] = getdate(today())

	days = counted_leave_days(employee, counted_from)
	new_end = add_working_days(employee, original, days)
	old_end = getdate(row.contract_end_date) if row.contract_end_date else None
	if old_end != new_end:
		updates["contract_end_date"] = new_end
	if updates:
		frappe.db.set_value("Employee", employee, updates)
	if "contract_end_date" in updates:
		frappe.get_doc("Employee", employee).add_comment(
			"Info",
			_("Contract end moved from {0} to {1} ({2} leave days counted since {3}{4}).").format(
				formatdate(old_end) if old_end else _("none"),
				formatdate(new_end),
				days,
				formatdate(counted_from),
				_("; latest {0}").format(reference) if reference else "",
			),
		)


def on_leave_change(doc, method=None):
	"""Leave Application on_submit / on_cancel."""
	if doc.status == "Approved" or doc.docstatus == 2:
		recalculate_end_date(doc.employee, doc.name)


def start_counting(employee_doc) -> None:
	"""Begins the rule for an employee: the end date as it is now, counting leave from today."""
	if not employee_doc.get("original_contract_end_date"):
		employee_doc.original_contract_end_date = employee_doc.get("contract_end_date")
	if not employee_doc.get("leave_counted_from"):
		employee_doc.leave_counted_from = getdate(today())


def start_counting_for_types(employment_types) -> None:
	"""HR added these types to the list: their employees start counting leave from today."""
	if not employment_types:
		return
	for name in frappe.get_all(
		"Employee",
		filters={"employment_type": ("in", list(employment_types)), "status": "Active"},
		pluck="name",
	):
		row = frappe.db.get_value(
			"Employee",
			name,
			["contract_end_date", "original_contract_end_date", "leave_counted_from"],
			as_dict=True,
		)
		updates = {}
		if not row.original_contract_end_date and row.contract_end_date:
			updates["original_contract_end_date"] = row.contract_end_date
		if not row.leave_counted_from:
			updates["leave_counted_from"] = getdate(today())
		if updates:
			frappe.db.set_value("Employee", name, updates)


def validate_employee(doc, method=None):
	"""Employee validate: only HR changes the two fields; a renewal restarts the count."""
	before = doc.get_doc_before_save()
	if before and any(doc.has_value_changed(field) for field in TRACKED_FIELDS):
		if not set(HR_ROLES) & set(frappe.get_roles()):
			frappe.throw(
				_("Only HR can change the original contract end date or when leave is counted from.")
			)

	if not uses_leave_end_date(doc.name, doc.employment_type):
		return

	type_changed = not before or before.employment_type != doc.employment_type
	end_edited = before and doc.has_value_changed("contract_end_date")
	tracked_edited = before and any(doc.has_value_changed(field) for field in TRACKED_FIELDS)
	if type_changed:
		# just became an employee without leave allocation: a fresh start from the end date as it is
		doc.original_contract_end_date = doc.contract_end_date
		doc.leave_counted_from = getdate(today())
	elif not (doc.get("original_contract_end_date") and doc.get("leave_counted_from")):
		# the two fields were cleared: start again from the end date as it is
		start_counting(doc)
	elif end_edited and not tracked_edited:
		# HR set a new end date by hand (a renewal): it becomes the original, counting restarts today
		doc.original_contract_end_date = doc.contract_end_date
		doc.leave_counted_from = getdate(today())
	elif tracked_edited and doc.original_contract_end_date and not doc.is_new():
		days = counted_leave_days(doc.name, doc.leave_counted_from or today())
		doc.contract_end_date = add_working_days(doc.name, doc.original_contract_end_date, days)


def refuse_allocation(doc, method=None):
	"""Leave Allocation / Leave Policy Assignment validate."""
	employment_type = frappe.db.get_value("Employee", doc.employee, "employment_type")
	if uses_leave_end_date(doc.employee, employment_type):
		frappe.throw(
			_(
				"{0} is a {1} employee. {1} is set as an Employee Type without Leave Allocation in HR Settings, so they get no leave allocation."
			).format(frappe.bold(doc.get("employee_name") or doc.employee), frappe.bold(employment_type)),
			title=_("No leave allocation for this employee type"),
		)


def leave_types_without_allocation() -> list[str]:
	"""Leave types an employee without allocation can use: Allow Negative Balance, not unpaid."""
	return frappe.get_all(
		"Leave Type", filters={"allow_negative": 1, "is_lwp": 0}, pluck="name", order_by="name"
	)
