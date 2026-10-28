# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Data for the employee app (/hr): the user's notifications and a month of their own attendance."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, get_datetime, getdate, strip_html

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
		order_by="creation desc, name desc",
		start=cint(start),
		page_length=min(cint(limit) or 20, 100),  # a page at a time: the app asks with start
	)


@frappe.whitelist(methods=["POST"])
def mark_notification_as_read(name: str | int) -> None:  # PWA Notification names are numbers
	if frappe.db.get_value("PWA Notification", name, "to_user") != frappe.session.user:
		frappe.throw(_("This notification is not yours."), frappe.PermissionError)
	frappe.db.set_value("PWA Notification", name, "read", 1, update_modified=False)


# Attendance
@frappe.whitelist()
def get_attendance_month(from_date: str, to_date: str, employee: str | None = None) -> list[dict]:
	"""Each day between the dates for the session employee, or for someone on their team (supervisors)."""
	from hrms.hr.supervisors import get_viewable_employee

	from_date, to_date = getdate(from_date), getdate(to_date)
	if date_diff(to_date, from_date) > 62:
		frappe.throw(_("Ask for at most two months at a time."))
	return get_attendance_days(get_viewable_employee(employee), from_date, to_date)


def get_attendance_days(employee: str, from_date, to_date) -> list[dict]:
	"""Each day between the dates: attendance, first check-in and holiday."""
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
		if holiday and row.get("status") == "On Leave":
			# leave types that count holidays mark them On Leave too; a holiday is shown as a holiday
			row = {}
		days.append(
			frappe._dict(
				date=date,
				status=row.get("status"),
				late_entry=cint(row.get("late_entry")),
				early_exit=cint(row.get("early_exit")),
				leave_type=row.get("leave_type"),
				shift=row.get("shift"),
				checked_in_at=first_in.get(date),
				holiday=holiday.get("description"),
				weekly_off=cint(holiday.get("weekly_off")),
			)
		)
		date = add_days(date, 1)
	return days


def count_attendance(days: list[dict]) -> dict:
	"""Days up to today by kind, as the Attendance page colours them."""
	today = getdate()
	counts = {"on_time": 0, "late": 0, "on_leave": 0, "absent": 0, "no_checkin": 0}
	for day in days:
		if day.date > today:
			continue
		if day.status == "On Leave":
			counts["on_leave"] += 1
		elif day.status == "Absent":
			counts["absent"] += 1
		elif day.status == "Half Day" or (day.status and day.late_entry):
			counts["late"] += 1
		elif day.status or day.checked_in_at:
			counts["on_time"] += 1
		elif not day.holiday and day.date < today:
			counts["no_checkin"] += 1
	return counts


# Team history: for supervisors (the leave approvers of departments)
@frappe.whitelist()
def get_team_attendance(from_date: str, to_date: str) -> list[dict]:
	"""Each team member's days between the dates, counted by kind."""
	from hrms.hr.supervisors import get_team

	from_date, to_date = getdate(from_date), getdate(to_date)
	if date_diff(to_date, from_date) > 62:
		frappe.throw(_("Ask for at most two months at a time."))
	return [
		{
			"employee": member.name,
			"employee_name": member.employee_name,
			"department": member.department,
			"counts": count_attendance(get_attendance_days(member.name, from_date, to_date)),
		}
		for member in get_team(frappe.session.user)
	]


@frappe.whitelist()
def get_team_leave_history(employee: str | None = None, status: str | None = None, limit: int = 100) -> dict:
	"""The team's leave requests, newest first: waiting, approved, rejected and cancelled."""
	from hrms.hr.doctype.leave_application.leave_calendar import get_leave_label
	from hrms.hr.supervisors import get_team

	team = get_team(frappe.session.user)
	names = [member.name for member in team]
	if employee:
		names = [name for name in names if name == employee]

	filters = {"employee": ("in", names or [""])}
	if status == "Cancelled":
		filters["docstatus"] = 2
	elif status:
		filters.update({"status": status, "docstatus": ("!=", 2)})
	requests = frappe.get_all(
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
			"status",
			"docstatus",
			"description",
			"leave_approver_name",
			"amended_from",
		],
		order_by="from_date desc, creation desc",
		limit=min(cint(limit) or 100, 300),
	)

	approvers = {}
	for row in frappe.get_all(
		"Leave Application Approver",
		filters={"parenttype": "Leave Application", "parent": ("in", [r.name for r in requests] or [""])},
		fields=["parent", "approver_name", "approver", "approval_level", "decision"],
		order_by="idx",
	):
		approvers.setdefault(row.parent, []).append(row)
	for row in requests:
		if row.docstatus == 2:
			row.status = "Cancelled"
		row.label = get_leave_label(row.employee, row.leave_type)
		row.approvers = approvers.get(row.name, [])

	return {
		"employees": [
			{"employee": m.name, "employee_name": m.employee_name, "department": m.department} for m in team
		],
		"requests": requests,
	}


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


# Employee Types without Leave Allocation: leave pushes the end date
@frappe.whitelist()
def get_end_date_details(days: float = 0) -> dict | None:
	"""The session employee's contract end date, and where `days` more leave would put it."""
	from hrms.hr.doctype.leave_application.leave_end_date import end_date_details

	return end_date_details(get_current_employee(), flt(days))


# Fixed-length leave types: where a leave starting on a date ends
@frappe.whitelist()
def get_fixed_leave_end(leave_type: str, from_date: str) -> str | None:
	from hrms.hr.doctype.leave_application.leave_fixed_length import fixed_end_date

	end = fixed_end_date(get_current_employee(), leave_type, from_date)
	return str(end) if end else None


# The leave form's "Goes to" line: the employee's own approvers, without needing read on Department
@frappe.whitelist()
def get_my_leave_approval_details() -> dict:
	from hrms.api import leave_approval_details

	return leave_approval_details(get_current_employee())


# Check-in: the office of today's shift, so the app can warn before an out-of-range check-in
@frappe.whitelist()
def get_my_checkin_location() -> dict | None:
	from hrms.hr.doctype.shift_assignment.shift_assignment import get_employee_shift
	from hrms.hr.office_range import OUTSIDE_OFFICE_REASONS, get_checkin_location

	employee = get_current_employee()
	now = frappe.utils.now_datetime()
	shift = get_employee_shift(employee, now, True) or {}
	shift_type = shift.get("shift_type")
	location = get_checkin_location(employee, shift_type.name if shift_type else None, now)
	if not location:
		return None
	return {
		"name": location.name,
		"latitude": location.latitude,
		"longitude": location.longitude,
		"radius": location.radius,
		"reasons": OUTSIDE_OFFICE_REASONS,
	}


# Employee Schedule: everyone's shifts for a week, read-only for every employee (staff can't read others'
# Shift Assignments)
@frappe.whitelist()
def get_roster(start_date: str | None = None, days: int = 7) -> dict:
	from hrms.hr.workforce_today import get_active_employees, get_leave_on

	get_current_employee()
	days = min(max(cint(days) or 7, 1), 31)
	start = getdate(start_date or frappe.utils.today())
	end = add_days(start, days - 1)
	dates = [add_days(start, n) for n in range(days)]

	employees = get_active_employees()
	names = [e.name for e in employees]
	default_shifts = dict(
		frappe.get_all(
			"Employee", filters={"name": ("in", names or [""])}, fields=["name", "default_shift"], as_list=True
		)
	)
	assignments = {}
	for row in frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": ("in", names or [""]),
			"docstatus": 1,
			"status": "Active",
			"start_date": ("<=", end),
		},
		or_filters=[["end_date", ">=", start], ["end_date", "is", "not set"]],
		fields=["employee", "shift_type", "shift_location", "start_date", "end_date"],
		order_by="start_date desc",
	):
		assignments.setdefault(row.employee, []).append(row)

	on_leave = {}
	for row in get_leave_on(names, start, end):
		on_leave.setdefault(row.employee, []).append(row)

	holidays_by_list = {}
	shift_types = set()
	rows = []
	for employee in employees:
		holiday_list = get_holiday_list_for_employee(employee.name, raise_exception=False)
		if holiday_list not in holidays_by_list:
			holidays_by_list[holiday_list] = (
				{
					row.holiday_date: frappe._dict(
						description=strip_html(row.description or "").strip(), weekly_off=row.weekly_off
					)
					for row in frappe.get_all(
						"Holiday",
						filters={"parent": holiday_list, "holiday_date": ("between", [start, end])},
						fields=["holiday_date", "description", "weekly_off"],
					)
				}
				if holiday_list
				else {}
			)
		holidays = holidays_by_list[holiday_list]

		cells = []
		for date in dates:
			assignment = next(
				(
					a
					for a in assignments.get(employee.name, [])
					if getdate(a.start_date) <= date and (not a.end_date or getdate(a.end_date) >= date)
				),
				None,
			)
			shift = assignment.shift_type if assignment else default_shifts.get(employee.name)
			holiday = holidays.get(date)
			leave = next(
				(
					l
					for l in on_leave.get(employee.name, [])
					if getdate(l.from_date) <= date <= getdate(l.to_date)
				),
				None,
			)
			if shift:
				shift_types.add(shift)
			cells.append(
				{
					"date": date,
					"shift": shift,
					"location": assignment.shift_location if assignment else None,
					# a holiday inside a leave is still a holiday, not a leave day
					"on_leave": bool(leave) and not holiday,
					"holiday": holiday.description if holiday and not holiday.weekly_off else None,
					"day_off": bool(holiday and holiday.weekly_off),
				}
			)
		rows.append(
			{
				"employee": employee.name,
				"employee_name": employee.employee_name,
				"department": employee.department,
				"image": employee.image,
				"days": cells,
			}
		)

	return {
		"dates": dates,
		"employees": rows,
		"shift_types": {
			row.name: row
			for row in frappe.get_all(
				"Shift Type",
				filters={"name": ("in", list(shift_types) or [""])},
				fields=["name", "start_time", "end_time", "color"],
			)
		},
	}


# Cuti Pengganti: days off for overtime
@frappe.whitelist()
def get_my_cuti_pengganti() -> dict:
	from hrms.hr.doctype.compensatory_leave_request.cuti_pengganti import get_summary

	return get_summary(get_current_employee())


@frappe.whitelist(methods=["POST"])
def request_cuti_pengganti(
	work_dates: list[str] | str | None = None, reason: str | None = None, work_date: str | None = None
) -> list[str]:
	"""Overtime Submission: one request per holiday worked, all sent or none."""
	from hrms.hr.doctype.compensatory_leave_request.cuti_pengganti import get_leave_type

	if not get_leave_type():
		frappe.throw(_("Overtime Submission isn't set up yet. Ask HR."))
	if not (reason or "").strip():
		frappe.throw(_("Say what the overtime was for."))
	dates = frappe.parse_json(work_dates) if isinstance(work_dates, str) else work_dates
	dates = sorted({getdate(date) for date in (dates or ([work_date] if work_date else []))})
	if not dates:
		frappe.throw(_("Pick the holidays you worked."))
	if len(dates) > 31:
		frappe.throw(_("Send at most 31 days at a time."))

	employee = get_current_employee()
	names = []
	for date in dates:
		doc = frappe.get_doc(
			{
				"doctype": "Compensatory Leave Request",
				"employee": employee,
				"leave_type": get_leave_type(),
				"work_from_date": date,
				"work_end_date": date,
				"reason": reason.strip(),
			}
		)
		doc.insert()
		names.append(doc.name)
	return names


@frappe.whitelist()
def get_my_holidays(from_date: str, to_date: str) -> list[dict]:
	"""The employee's holidays (public holidays and weekly days off) between the dates."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	if date_diff(to_date, from_date) > 62:
		frappe.throw(_("Ask for at most two months at a time."))
	holidays = get_holidays_between(get_current_employee(), from_date, to_date)
	return [
		{"date": date, "description": row.description, "weekly_off": cint(row.weekly_off)}
		for date, row in sorted(holidays.items())
	]


@frappe.whitelist(methods=["POST"])
def withdraw_cuti_pengganti(name: str) -> None:
	"""The employee takes back a request nobody has decided on yet."""
	doc = frappe.get_doc("Compensatory Leave Request", name)
	if doc.employee != get_current_employee():
		frappe.throw(_("This is not your request."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != "Open" or any(r.decision != "Pending" for r in doc.approvers):
		frappe.throw(_("A supervisor has already decided on this request, so it can't be withdrawn."))
	frappe.delete_doc("Compensatory Leave Request", name, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def decide_cuti_pengganti(name: str, decision: str) -> str:
	from hrms.hr.doctype.compensatory_leave_request.cuti_pengganti import record_decision

	if decision not in ("Approved", "Rejected"):
		frappe.throw(_("Decision must be Approved or Rejected."))
	# lock the request so two supervisors deciding at the same time both count
	frappe.db.get_value("Compensatory Leave Request", name, "name", for_update=True)
	return record_decision(frappe.get_doc("Compensatory Leave Request", name), decision)


# Changing or cancelling an approved leave: the employee asks after talking to HR; HR decides
@frappe.whitelist(methods=["POST"])
def request_leave_change(
	leave_application: str,
	change: str,
	reason: str,
	informed_hr: int = 0,
	understands_waiting: int = 0,
	new_from_date: str | None = None,
	new_to_date: str | None = None,
) -> str:
	if frappe.db.get_value("Leave Application", leave_application, "employee") != get_current_employee():
		frappe.throw(_("This is not your leave."), frappe.PermissionError)
	if not (reason or "").strip():
		frappe.throw(_("Say why the leave needs to change."))
	doc = frappe.get_doc(
		{
			"doctype": "Leave Change Request",
			"leave_application": leave_application,
			"change": change,
			"new_from_date": getdate(new_from_date) if new_from_date else None,
			"new_to_date": getdate(new_to_date) if new_to_date else None,
			"reason": reason.strip(),
			"informed_hr": cint(informed_hr),
			"understands_waiting": cint(understands_waiting),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def get_my_leave_changes(leave_application: str | None = None) -> list[dict]:
	"""The session employee's change requests, newest first; for one leave, also the one that made it."""
	filters = {"employee": get_current_employee()}
	or_filters = None
	if leave_application:
		or_filters = {"leave_application": leave_application, "new_leave_application": leave_application}
	return frappe.get_all(
		"Leave Change Request",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name",
			"leave_application",
			"leave_type",
			"from_date",
			"to_date",
			"change",
			"new_from_date",
			"new_to_date",
			"reason",
			"status",
			"hr_note",
			"decided_on",
			"new_leave_application",
			"creation",
		],
		order_by="creation desc",
		limit=20,
	)


@frappe.whitelist(methods=["POST"])
def withdraw_leave_change(name: str) -> None:
	"""The employee takes back a request HR hasn't decided on yet."""
	doc = frappe.get_doc("Leave Change Request", name)
	if doc.employee != get_current_employee():
		frappe.throw(_("This is not your request."), frappe.PermissionError)
	if doc.status != "Open":
		frappe.throw(_("HR has already decided on this request."))
	frappe.delete_doc("Leave Change Request", name, ignore_permissions=True)
