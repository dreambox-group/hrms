# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Leave types with a fixed length (HR Settings), e.g. Sick Leave = 2 days, After-birth Leave = 3 months.

A request of such a type is always exactly that long: its end date is set from the start date, in
the employee app and in the desk alike. Days count the way the leave type counts days (working days,
or calendar days with "Include holidays"); months are calendar months (1 Nov + 3 months = 31 Jan).
These types need no leave allocation; if HR allocates one anyway, its balance applies as usual.
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate

from hrms.utils.holiday_list import get_holiday_dates_between_range

SETTINGS_FIELD = "leave_types_with_fixed_length"


def get_fixed_lengths() -> dict[str, dict]:
	rows = frappe.get_all(
		"HR Settings Fixed Leave Length",
		filters={"parenttype": "HR Settings", "parentfield": SETTINGS_FIELD},
		fields=["leave_type", "length", "unit"],
		order_by="idx",
	)
	unpaid = set(
		frappe.get_all(
			"Leave Type",
			filters={"name": ("in", [r.leave_type for r in rows] or [""]), "is_lwp": 1},
			pluck="name",
		)
	)
	for row in rows:
		row.is_lwp = int(row.leave_type in unpaid)
	return {row.leave_type: row for row in rows}


def get_fixed_length(leave_type: str | None) -> dict | None:
	return get_fixed_lengths().get(leave_type) if leave_type else None


def fixed_end_date(employee: str, leave_type: str, from_date):
	"""The last day of a fixed-length leave starting on `from_date`, or None for other leave types."""
	rule = get_fixed_length(leave_type)
	if not rule or not from_date or cint(rule.length) <= 0:
		return None
	start, length = getdate(from_date), cint(rule.length)
	if rule.unit == "Months":
		return add_days(add_months(start, length), -1)
	if cint(frappe.db.get_value("Leave Type", leave_type, "include_holiday")):
		return add_days(start, length - 1)

	# working days: skip the employee's holidays, as the leave's day count does
	holidays = {
		getdate(d)
		for d in get_holiday_dates_between_range(
			employee, start, add_days(start, length * 3 + 45), raise_exception_for_holiday_list=False
		)
	}
	date, counted = start, 0
	while True:
		if date not in holidays:
			counted += 1
			if counted >= length:
				return date
		date = add_days(date, 1)


def apply_fixed_length(doc) -> None:
	"""Leave Application validate: a fixed-length leave gets its exact end date and no half day."""
	if doc.docstatus != 0 or not doc.from_date:
		return
	end = fixed_end_date(doc.employee, doc.leave_type, doc.from_date)
	if not end:
		return
	doc.half_day = 0
	doc.half_day_date = None
	doc.to_date = end


def describe(rule) -> str:
	length = cint(rule.length)
	if rule.unit == "Months":
		return _("1 month") if length == 1 else _("{0} months").format(length)
	return _("1 day") if length == 1 else _("{0} days").format(length)


def validate_settings(settings) -> None:
	"""HR Settings validate: one length per leave type, more than zero."""
	seen = set()
	for row in settings.get(SETTINGS_FIELD) or []:
		if row.leave_type in seen:
			frappe.throw(
				_("{0} is in Leave Types with a Fixed Length twice.").format(frappe.bold(row.leave_type))
			)
		seen.add(row.leave_type)
		if cint(row.length) <= 0:
			frappe.throw(
				_("The fixed length of {0} must be more than zero.").format(frappe.bold(row.leave_type))
			)
