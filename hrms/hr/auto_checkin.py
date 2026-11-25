# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Automatic Check-in (owner, 24 Nov 2026).

An employee with "Automatic Check-in" ticked (Employee > Attendance & Leaves, HR only) is checked
in at the start of their shift and out at its end, every working day, by the scheduler (every 10
minutes). The check-in is on time (exactly the shift's start). An office shift (its Shift Location
has a radius and coordinates, see hrms.hr.office_range) gets the office's coordinates; a shift
without one (working from home) gets no location.

Skipped, for that day: approved leave or any submitted attendance already there, a holiday on the
shift's (or else the employee's) holiday list, no shift (no active Shift Assignment and no Default
Shift), not yet joined or already relieved, and any check-in of their own in that shift (then the
person checks in and out themselves that day).

Every such log has Device ID "Auto check-in", so HR can tell them apart. Only today's check-in is
made, never an earlier day's; yesterday's check-out is still made when yesterday's automatic
check-in is there (a night shift, or a run missed around midnight).
"""

from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime

AUTO_DEVICE = "Auto check-in"
FIELD = "auto_checkin"
HR_ROLES = {"HR Manager", "HR User", "System Manager"}


# --- the Employee field: only HR may change it ---------------------------------------------------
def validate_employee(doc, method=None):
	"""Employee validate hook. Staff may edit parts of their own record (Employee Self Service), but
	not this: it would excuse them from checking in."""
	if not doc.get(FIELD) and doc.is_new():
		return
	if not doc.has_value_changed(FIELD) or frappe.session.user == "Administrator":
		return
	if HR_ROLES & set(frappe.get_roles()):
		return
	frappe.throw(_("Only HR can change Automatic Check-in."), frappe.PermissionError)


# --- the scheduler job ---------------------------------------------------------------------------
def run(now: datetime | None = None):
	"""Every 10 minutes (hooks.scheduler_events). One employee's failure is logged and skipped."""
	if not frappe.db.has_column("Employee", FIELD):
		return
	now = get_datetime(now) if now else now_datetime()
	today = now.date()
	for employee in frappe.get_all(
		"Employee", filters={FIELD: 1, "status": "Active"}, fields=["name", "date_of_joining", "relieving_date"]
	):
		try:
			process_employee(employee, now, today)
			frappe.db.commit()  # nosemgrep: one employee at a time, so one failure does not undo the rest
		except Exception:
			frappe.db.rollback()
			frappe.log_error(f"Automatic check-in failed for {employee.name}", reference_doctype="Employee", reference_name=employee.name)


def process_employee(employee, now: datetime, today: date) -> list[str]:
	"""Makes what is due for the employee now; returns the names of the logs made (for tests)."""
	made = []
	# yesterday: only the check-out of an automatic check-in already there
	for day, make_in in ((add_days(today, -1), False), (today, True)):
		day = getdate(day)
		if not works_that_day(employee, day):
			continue
		for shift in shifts_on(employee.name, day):
			made += process_shift(employee.name, day, shift, now, make_in)
	return made


def works_that_day(employee, day: date) -> bool:
	if employee.date_of_joining and getdate(employee.date_of_joining) > day:
		return False
	if employee.relieving_date and getdate(employee.relieving_date) < day:
		return False
	return True


def shifts_on(employee: str, day: date) -> list[frappe._dict]:
	"""The employee's shifts starting on the day: active Shift Assignments, else the Default Shift."""
	names = frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee, "docstatus": 1, "status": "Active", "start_date": ["<=", day]},
		or_filters=[["end_date", ">=", day], ["end_date", "=", None]],  # not "is not set": on Postgres that compares the date to ""
		pluck="shift_type",
	)
	if not names:
		default = frappe.db.get_value("Employee", employee, "default_shift")
		names = [default] if default else []
	shifts = []
	for name in dict.fromkeys(names):
		shift = frappe.get_cached_value(
			"Shift Type",
			name,
			["name", "start_time", "end_time", "holiday_list", "begin_check_in_before_shift_start_time",
			 "allow_check_out_after_shift_end_time"],
			as_dict=True,
		)
		if not shift or shift.start_time is None or shift.end_time is None:
			continue
		midnight = datetime.combine(day, datetime.min.time())
		shift.start = midnight + shift.start_time
		shift.end = midnight + shift.end_time
		if shift.end <= shift.start:  # a night shift ends the next day
			shift.end += timedelta(days=1)
		shifts.append(shift)
	return shifts


def is_day_off(employee: str, day: date, shift) -> bool:
	"""Leave, attendance already marked (leave, attendance request, by hand) or a holiday."""
	if frappe.db.exists("Attendance", {"employee": employee, "attendance_date": day, "docstatus": 1}):
		return True
	if frappe.db.exists(
		"Leave Application",
		{
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
	):
		return True
	from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday

	from hrms.utils.holiday_list import get_holiday_list_for_employee

	holiday_list = shift.holiday_list or get_holiday_list_for_employee(employee, raise_exception=False, as_on=day)
	return bool(holiday_list and is_holiday(holiday_list, day))


def process_shift(employee: str, day: date, shift, now: datetime, make_in: bool) -> list[str]:
	if now < shift.start:
		return []
	before = timedelta(minutes=max(cint(shift.begin_check_in_before_shift_start_time), 60))
	after = timedelta(minutes=max(cint(shift.allow_check_out_after_shift_end_time), 60))
	logs = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [shift.start - before, shift.end + after]]},
		fields=["name", "log_type", "device_id"],
	)
	# the person checked in themselves: they also check out themselves that day
	if any(log.device_id != AUTO_DEVICE for log in logs):
		return []
	auto_in = any(log.log_type == "IN" for log in logs)
	auto_out = any(log.log_type == "OUT" for log in logs)

	made = []
	if not auto_in:
		if not make_in or is_day_off(employee, day, shift):
			return []
		made.append(make_log(employee, "IN", shift.start, shift.name))
		auto_in = True
	if auto_in and not auto_out and now >= shift.end:
		made.append(make_log(employee, "OUT", shift.end, shift.name))
	return made


def make_log(employee: str, log_type: str, time: datetime, shift_type: str) -> str:
	from hrms.hr.office_range import get_checkin_location

	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee
	doc.log_type = log_type
	doc.time = time
	doc.device_id = AUTO_DEVICE
	office = get_checkin_location(employee, shift_type, time)
	if office:  # an office shift: at the office
		doc.latitude = flt(office.latitude)
		doc.longitude = flt(office.longitude)
	doc.flags.auto_checkin = True
	doc.insert(ignore_permissions=True)
	return doc.name
