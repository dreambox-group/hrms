# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Data for the employee app (/hr): the user's notifications and a month of their own attendance."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, get_datetime, getdate, strip_html

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

from hrms.api import get_current_employee

NOTIFICATION_FIELDS = [
	"name",
	"from_user",
	"message",
	"read",
	"creation",
	"reference_document_type",
	"reference_document_name",
]


# Notifications: read by the user filter, not PWA Notification permissions, which not every
# employee's roles grant (the list failed with a permission error while the unread count worked)
@frappe.whitelist()
def get_notifications(start: int = 0, limit: int = 20) -> list[dict]:
	return frappe.get_all(
		"PWA Notification",
		filters={"to_user": frappe.session.user},
		fields=NOTIFICATION_FIELDS,
		order_by="creation desc",
		start=cint(start),
		page_length=min(cint(limit) or 20, 100),
	)


@frappe.whitelist(methods=["POST"])
def mark_notification_as_read(name: str | int) -> None:  # PWA Notification names are numbers
	if frappe.db.get_value("PWA Notification", name, "to_user") != frappe.session.user:
		frappe.throw(_("This notification is not yours."), frappe.PermissionError)
	frappe.db.set_value("PWA Notification", name, "read", 1, update_modified=False)


# Attendance
@frappe.whitelist()
def get_attendance_month(from_date: str, to_date: str) -> list[dict]:
	"""Each day between the dates for the session employee: attendance, first check-in and holiday."""
	employee = get_current_employee()
	from_date, to_date = getdate(from_date), getdate(to_date)
	if date_diff(to_date, from_date) > 62:
		frappe.throw(_("Ask for at most two months at a time."))

	attendance = {
		row.attendance_date: row
		for row in frappe.get_all(
			"Attendance",
			filters={
				"employee": employee,
				"docstatus": 1,
				"attendance_date": ("between", [from_date, to_date]),
			},
			fields=["attendance_date", "status", "late_entry", "early_exit", "leave_type", "shift"],
		)
	}

	first_in = {}
	for log in frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ("between", [get_datetime(from_date), get_datetime(add_days(to_date, 1))]),
		},
		fields=["time", "log_type"],
		order_by="time",
	):
		if log.log_type != "OUT":
			first_in.setdefault(getdate(log.time), log.time)

	holidays = get_holidays_between(employee, from_date, to_date)

	days = []
	date = from_date
	while date <= to_date:
		row = attendance.get(date) or {}
		holiday = holidays.get(date) or {}
		days.append(
			{
				"date": date,
				"status": row.get("status"),
				"late_entry": cint(row.get("late_entry")),
				"early_exit": cint(row.get("early_exit")),
				"leave_type": row.get("leave_type"),
				"shift": row.get("shift"),
				"checked_in_at": first_in.get(date),
				"holiday": holiday.get("description"),
				"weekly_off": cint(holiday.get("weekly_off")),
			}
		)
		date = add_days(date, 1)
	return days


def get_holidays_between(employee: str, from_date, to_date) -> dict:
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return {}
	return {
		row.holiday_date: frappe._dict(
			description=strip_html(row.description or "").strip(), weekly_off=row.weekly_off
		)
		for row in frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": ("between", [from_date, to_date])},
			fields=["holiday_date", "description", "weekly_off"],
		)
	}


# Holidays: read for the session employee's own list, which employees can't open directly
@frappe.whitelist()
def get_upcoming_holidays(limit: int = 50) -> list[dict]:
	return get_upcoming_holidays_for(get_current_employee(), limit)


def get_upcoming_holidays_for(employee: str, limit: int = 50) -> list[dict]:
	"""Public holidays (not weekly days off) from today on, earliest first."""
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return []
	holidays = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "holiday_date": (">=", getdate()), "weekly_off": 0},
		fields=["holiday_date", "description"],
		order_by="holiday_date asc",
		limit=min(cint(limit) or 50, 200),
	)
	for holiday in holidays:
		holiday.description = strip_html(holiday.description or "").strip()
	return holidays
