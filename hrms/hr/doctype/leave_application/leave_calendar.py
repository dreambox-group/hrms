# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Approved leave on a shared Google Calendar, so everyone can see who is away.

With HR Settings > Leave Google Calendar set, each approved Leave Application gets an all-day Event
titled "<label> - <employee name>". The label comes from the employee's Employment Type (e.g. "Izin"
for interns), else the Leave Type's Calendar Label (e.g. "Cuti", "Izin Sakit"), else the leave type's
name. The reason is never shown. Cancelling the leave removes the event.

The event is sent to Google here rather than through Frappe's own Event sync, because that sync sends
an all-day event's last day as its end, which Google treats as exclusive (one day short), and its
errors would block the approval. Here a Google problem is logged and retried every night.
"""

import frappe
from frappe import _
from frappe.integrations.doctype.google_calendar.google_calendar import get_google_calendar_object
from frappe.utils import add_days, getdate, today
from frappe.utils.messages import clear_last_message


def get_leave_google_calendar() -> str | None:
	return frappe.db.get_single_value("HR Settings", "leave_google_calendar")


def get_leave_calendar_title(leave_application) -> str:
	employment_type = frappe.db.get_value("Employee", leave_application.employee, "employment_type")
	label = (
		(employment_type and frappe.db.get_value("Employment Type", employment_type, "leave_calendar_label"))
		or frappe.db.get_value("Leave Type", leave_application.leave_type, "calendar_label")
		or leave_application.leave_type
	)
	return f"{label} - {leave_application.employee_name}"


def add_to_leave_calendar(leave_application) -> bool:
	"""Returns False only when Google couldn't be reached."""
	if not (calendar := get_leave_google_calendar()):
		return True

	# imported history only needs events for leave that is still ahead
	if frappe.flags.in_import and getdate(leave_application.to_date) < getdate(today()):
		return True

	if frappe.db.exists(
		"Event", {"reference_doctype": "Leave Application", "reference_docname": leave_application.name}
	):
		return True

	event = frappe.get_doc(
		{
			"doctype": "Event",
			"subject": get_leave_calendar_title(leave_application),
			"event_category": "Event",
			"event_type": "Public",
			"all_day": 1,
			"starts_on": f"{leave_application.from_date} 00:00:00",
			"ends_on": f"{leave_application.to_date} 23:59:59",
			"reference_doctype": "Leave Application",
			"reference_docname": leave_application.name,
		}
	).insert(ignore_permissions=True)
	return push_to_google_calendar(event, calendar)


def push_to_google_calendar(event, calendar: str) -> bool:
	"""Adds the event to the Google Calendar. Never raises: a Google problem must not block an approval."""
	try:
		google_calendar, account = get_google_calendar_object(calendar)
		google_event = (
			google_calendar.events()
			.insert(
				calendarId=account.google_calendar_id,
				body={
					"summary": event.subject,
					"start": {"date": str(getdate(event.starts_on))},
					# Google's end date of an all-day event is exclusive
					"end": {"date": str(add_days(getdate(event.ends_on), 1))},
					# a colleague's leave doesn't make the calendar's owner busy
					"transparency": "transparent",
				},
			)
			.execute()
		)
	except Exception as e:
		if isinstance(e, frappe.ValidationError):
			clear_last_message()
		frappe.log_error(
			title=_("Leave not added to Google Calendar"),
			reference_doctype="Event",
			reference_name=event.name,
		)
		frappe.msgprint(
			_(
				"The leave was saved, but it couldn't be added to Google Calendar. It will be retried tonight."
			),
			indicator="orange",
			alert=True,
		)
		return False

	event.db_set(
		{
			"google_calendar": calendar,
			"google_calendar_id": account.google_calendar_id,
			"google_calendar_event_id": google_event["id"],
		},
		update_modified=False,
	)
	return True


def remove_from_leave_calendar(leave_application) -> None:
	for event in frappe.get_all(
		"Event",
		filters={"reference_doctype": "Leave Application", "reference_docname": leave_application.name},
		fields=["name", "google_calendar", "google_calendar_id", "google_calendar_event_id"],
	):
		if event.google_calendar and event.google_calendar_event_id:
			remove_from_google_calendar(event)
		# cleared so that Frappe's own Event delete hook doesn't go to Google as well
		frappe.db.set_value("Event", event.name, "google_calendar", None, update_modified=False)
		frappe.delete_doc("Event", event.name, ignore_permissions=True)


def remove_from_google_calendar(event) -> None:
	"""Never raises: a Google problem must not block cancelling the leave."""
	try:
		google_calendar, _account = get_google_calendar_object(event.google_calendar)
		google_calendar.events().delete(
			calendarId=event.google_calendar_id, eventId=event.google_calendar_event_id
		).execute()
	except Exception as e:
		if isinstance(e, frappe.ValidationError):
			clear_last_message()
		frappe.log_error(
			title=_("Leave not removed from Google Calendar"),
			reference_doctype="Event",
			reference_name=event.name,
		)
		frappe.msgprint(
			_(
				"The leave was cancelled, but it couldn't be removed from Google Calendar. Please delete it there."
			),
			indicator="orange",
			alert=True,
		)


def push_missing_leave_to_google_calendar() -> None:
	"""Approved leave from today onward that isn't on the current Google Calendar yet.

	Runs every night (retrying failed pushes) and when HR Settings' calendar changes.
	"""
	if not (calendar := get_leave_google_calendar()):
		return

	for name in frappe.get_all(
		"Leave Application",
		filters={"docstatus": 1, "status": "Approved", "to_date": (">=", today())},
		order_by="from_date",
		pluck="name",
	):
		event = frappe.db.get_value(
			"Event",
			{"reference_doctype": "Leave Application", "reference_docname": name},
			["name", "google_calendar", "google_calendar_event_id"],
			as_dict=True,
		)
		if not event:
			pushed = add_to_leave_calendar(frappe.get_doc("Leave Application", name))
		elif event.google_calendar != calendar or not event.google_calendar_event_id:
			pushed = push_to_google_calendar(frappe.get_doc("Event", event.name), calendar)
		else:
			continue

		# stop at the first failure: Google is down or the calendar's login has expired
		if not pushed:
			return
