# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_days, get_year_ending, get_year_start, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.leave_application.leave_calendar import push_missing_leave_to_google_calendar
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
CALENDAR = "_Test Leave Calendar"
GOOGLE_CALENDAR_ID = "leave@group.calendar.google.com"


class TestLeaveCalendar(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_google_calendar", CALENDAR)
		frappe.db.set_value("Leave Type", "_Test Leave Type", "calendar_label", "Cuti")
		frappe.db.set_value("Employment Type", "Intern", "leave_calendar_label", "Izin")
		delete_test_leave()

		self.google = FakeGoogleCalendar()
		patcher = patch(
			"hrms.hr.doctype.leave_application.leave_calendar.get_google_calendar_object",
			side_effect=lambda calendar: (self.google, frappe._dict(google_calendar_id=GOOGLE_CALENDAR_ID)),
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def tearDown(self):
		frappe.db.set_single_value("HR Settings", "leave_google_calendar", None)
		frappe.db.set_value("Leave Type", "_Test Leave Type", "calendar_label", None)
		frappe.db.set_value("Employment Type", "Intern", "leave_calendar_label", None)

	def test_approved_leave_is_added_to_google_calendar(self):
		employee = make_employee("lc.staff@example.com", COMPANY, employment_type="Full-time")
		application = approve_leave(employee, days=3)

		event = get_event(application)
		self.assertEqual(event.subject, f"Cuti - {application.employee_name}")
		self.assertEqual(event.google_calendar, CALENDAR)
		self.assertEqual(event.google_calendar_event_id, "google-1")

		calendar_id, body = self.google.inserted[0]
		self.assertEqual(calendar_id, GOOGLE_CALENDAR_ID)
		self.assertEqual(body["summary"], f"Cuti - {application.employee_name}")
		self.assertEqual(body["start"], {"date": str(application.from_date)})
		# the day after the last day, as Google's end date is exclusive
		self.assertEqual(body["end"], {"date": str(add_days(application.to_date, 1))})
		self.assertEqual(body["transparency"], "transparent")
		self.assertNotIn("description", body)

	def test_titles(self):
		intern = make_employee("lc.intern@example.com", COMPANY, employment_type="Intern")
		self.assertEqual(get_event(approve_leave(intern)).subject, f"Izin - {employee_name(intern)}")

		frappe.db.set_value("Leave Type", "_Test Leave Type", "calendar_label", None)
		staff = make_employee("lc.staff@example.com", COMPANY, employment_type="Full-time")
		self.assertEqual(
			get_event(approve_leave(staff)).subject, f"_Test Leave Type - {employee_name(staff)}"
		)

	def test_cancelled_leave_is_removed(self):
		application = approve_leave(make_employee("lc.staff@example.com", COMPANY))

		application.cancel()

		self.assertFalse(get_event(application))
		self.assertEqual(self.google.deleted, [(GOOGLE_CALENDAR_ID, "google-1")])

	def test_google_failure_does_not_block_the_approval(self):
		self.google.fail = True
		application = approve_leave(make_employee("lc.staff@example.com", COMPANY))

		self.assertEqual(frappe.db.get_value("Leave Application", application.name, "docstatus"), 1)
		self.assertFalse(get_event(application).google_calendar_event_id)
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"reference_doctype": "Event", "reference_name": get_event(application).name}
			)
		)

		# the nightly retry adds it once Google works again
		self.google.fail = False
		push_missing_leave_to_google_calendar()
		self.assertIn(get_event(application).google_calendar_event_id, self.google.ids_for(application))

	def test_no_calendar_set(self):
		frappe.db.set_single_value("HR Settings", "leave_google_calendar", None)
		application = approve_leave(make_employee("lc.staff@example.com", COMPANY))

		self.assertFalse(get_event(application))
		self.assertFalse(self.google.inserted)

	def test_rejected_leave_is_not_added(self):
		application = approve_leave(make_employee("lc.staff@example.com", COMPANY), status="Rejected")

		self.assertFalse(get_event(application))

	def test_upcoming_leave_is_added_when_the_calendar_is_set(self):
		frappe.db.set_single_value("HR Settings", "leave_google_calendar", None)
		application = approve_leave(make_employee("lc.staff@example.com", COMPANY))
		self.assertFalse(get_event(application))

		frappe.db.set_single_value("HR Settings", "leave_google_calendar", CALENDAR)
		push_missing_leave_to_google_calendar()

		self.assertIn(get_event(application).google_calendar_event_id, self.google.ids_for(application))
		# nothing is sent twice (other tests' approved leave may be pushed by the same run)
		sent = len(self.google.inserted)
		push_missing_leave_to_google_calendar()
		self.assertEqual(len(self.google.inserted), sent)
		self.assertEqual(len(self.google.ids_for(application)), 1)


class FakeGoogleCalendar:
	def __init__(self):
		self.fail = False
		self.inserted = []
		self.deleted = []

	def events(self):
		return self

	def insert(self, calendarId, body):
		if self.fail:
			raise ConnectionError("Google is unreachable")
		self.inserted.append((calendarId, body))
		return FakeRequest({"id": f"google-{len(self.inserted)}"})

	def ids_for(self, application):
		"""Google ids of the events sent for this leave application."""
		title = f" - {application.employee_name}"
		return [
			f"google-{i}"
			for i, (_calendar, body) in enumerate(self.inserted, start=1)
			if body["summary"].endswith(title) and body["start"]["date"] == str(application.from_date)
		]

	def delete(self, calendarId, eventId):
		self.deleted.append((calendarId, eventId))
		return FakeRequest({})


class FakeRequest:
	def __init__(self, result):
		self.result = result

	def execute(self):
		return self.result


def delete_test_leave():
	employees = frappe.get_all("Employee", filters={"user_id": ("like", "lc.%@example.com")}, pluck="name")
	if not employees:
		return

	applications = frappe.get_all("Leave Application", filters={"employee": ("in", employees)}, pluck="name")
	if applications:
		frappe.db.delete(
			"Event", {"reference_doctype": "Leave Application", "reference_docname": ("in", applications)}
		)
		frappe.db.delete("Leave Application", {"name": ("in", applications)})
	frappe.db.delete(
		"Leave Ledger Entry", {"employee": ("in", employees), "transaction_type": "Leave Application"}
	)


def approve_leave(employee, days=1, status="Approved"):
	from_date = get_working_day(employee)
	to_date = add_days(from_date, days - 1)
	if not frappe.db.exists(
		"Leave Allocation",
		{"employee": employee, "leave_type": "_Test Leave Type", "docstatus": 1, "to_date": (">=", to_date)},
	):
		make_allocation_record(
			employee, from_date=get_year_start(from_date), to_date=get_year_ending(from_date)
		)

	application = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": "_Test Leave Type",
			"from_date": from_date,
			"to_date": to_date,
			"company": COMPANY,
			"posting_date": nowdate(),
			"status": status,
		}
	).insert()
	application.submit()
	return application


def get_working_day(employee):
	"""A weekday with three more working days after it, so multi-day leave doesn't span a holiday."""
	date = add_days(getdate(), 7)
	holidays = {str(d) for d in get_holiday_dates_for_employee(employee, date, get_year_ending(date))}
	while any(str(add_days(date, i)) in holidays or add_days(date, i).weekday() >= 5 for i in range(3)):
		date = add_days(date, 1)
	return date


def get_event(application):
	return frappe.db.get_value(
		"Event",
		{"reference_doctype": "Leave Application", "reference_docname": application.name},
		["name", "subject", "google_calendar", "google_calendar_event_id"],
		as_dict=True,
	)


def employee_name(employee):
	return frappe.db.get_value("Employee", employee, "employee_name")
