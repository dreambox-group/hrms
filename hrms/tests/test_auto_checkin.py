# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Automatic Check-in (hrms.hr.auto_checkin; owner, 24 Nov 2026)."""

from datetime import datetime, time

import frappe
from frappe.utils import add_days, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr import auto_checkin as ac
from hrms.hr.doctype.employee_checkin.test_employee_checkin import make_shift_location
from hrms.hr.doctype.shift_type.test_shift_type import make_shift_assignment, setup_shift_type
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
HOLIDAYS = "_Test Auto Checkin Holidays"


class TestAutoCheckin(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		# as on production: selfie and location required for people checking themselves in
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 1)
		frappe.db.set_single_value("HR Settings", "require_selfie_for_checkin", 1)
		self.day = getdate()
		self.holiday = add_days(self.day, 1)
		if not frappe.db.exists("Holiday List", HOLIDAYS):
			frappe.get_doc(
				{
					"doctype": "Holiday List",
					"holiday_list_name": HOLIDAYS,
					"from_date": add_days(self.day, -30),
					"to_date": add_days(self.day, 30),
					"holidays": [{"holiday_date": self.holiday, "description": "Test holiday"}],
				}
			).insert()
		self.shift = setup_shift_type(
			shift_type="_Test Auto Checkin Shift", start_time="08:30:00", end_time="17:30:00"
		)
		self.shift.db_set("holiday_list", HOLIDAYS)
		self.office = frappe.db.get_value("Shift Location", "_Test AC Office") or make_shift_location(
			"_Test AC Office", -6.2088, 106.8456, 200
		).name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 0)
		frappe.db.set_single_value("HR Settings", "require_selfie_for_checkin", 0)

	def employee(self, email, office=True):
		name = make_employee(email, COMPANY)
		frappe.db.delete("Employee Checkin", {"employee": name})
		frappe.db.delete("Shift Assignment", {"employee": name})
		frappe.db.delete("Attendance", {"employee": name})
		frappe.db.set_value("Employee", name, {"auto_checkin": 1, "date_of_joining": add_days(self.day, -60)})
		make_shift_assignment(
			self.shift.name, name, add_days(self.day, -1), shift_location=self.office if office else None
		)
		return frappe.db.get_value("Employee", name, ["name", "date_of_joining", "relieving_date"], as_dict=True)

	def at(self, hour, minute=0, day=None):
		return datetime.combine(day or self.day, time(hour, minute))

	def logs(self, employee):
		return frappe.get_all(
			"Employee Checkin",
			filters={"employee": employee},
			fields=["log_type", "time", "device_id", "latitude", "longitude", "outside_office_range"],
			order_by="time asc",
		)

	def test_in_at_shift_start_and_out_at_shift_end_at_the_office(self):
		e = self.employee("ac.office@example.com")
		self.assertEqual(ac.process_employee(e, self.at(7), self.day), [])  # before the shift: nothing

		self.assertEqual(len(ac.process_employee(e, self.at(12), self.day)), 1)
		(log,) = self.logs(e.name)
		self.assertEqual((log.log_type, log.time, log.device_id), ("IN", self.at(8, 30), ac.AUTO_DEVICE))
		self.assertAlmostEqual(log.latitude, -6.2088)
		self.assertFalse(log.outside_office_range)

		self.assertEqual(len(ac.process_employee(e, self.at(18), self.day)), 1)
		self.assertEqual([(l.log_type, l.time) for l in self.logs(e.name)], [("IN", self.at(8, 30)), ("OUT", self.at(17, 30))])
		self.assertEqual(ac.process_employee(e, self.at(19), self.day), [])  # again: nothing new

	def test_working_from_home_has_no_location(self):
		e = self.employee("ac.home@example.com", office=False)
		ac.process_employee(e, self.at(12), self.day)
		(log,) = self.logs(e.name)
		self.assertFalse(log.latitude or log.longitude)

	def test_own_check_in_means_nothing_automatic_that_day(self):
		e = self.employee("ac.own@example.com")
		own = frappe.get_doc(
			{"doctype": "Employee Checkin", "employee": e.name, "log_type": "IN", "time": self.at(9),
			 "latitude": -6.2088, "longitude": 106.8456}
		)
		own.flags.selfie_checkin = True
		own.insert()
		self.assertEqual(ac.process_employee(e, self.at(18), self.day), [])

	def test_days_off_are_skipped(self):
		e = self.employee("ac.leave@example.com")
		frappe.get_doc(
			{"doctype": "Attendance", "employee": e.name, "attendance_date": self.day, "status": "On Leave",
			 "company": COMPANY}
		).submit()
		self.assertEqual(ac.process_employee(e, self.at(18), self.day), [])
		(shift,) = ac.shifts_on(e.name, self.day)
		self.assertTrue(ac.is_day_off(e.name, self.holiday, shift))
		self.assertFalse(ac.is_day_off(e.name, add_days(self.day, 2), shift))

	def test_no_check_in_for_an_earlier_day_or_before_joining(self):
		e = self.employee("ac.late@example.com")
		# just after midnight: yesterday's missed check-in is not made
		self.assertEqual(ac.process_employee(e, self.at(0, 20), self.day), [])
		e.date_of_joining = add_days(self.day, 1)
		self.assertEqual(ac.process_employee(e, self.at(12), self.day), [])

	def test_only_hr_can_change_the_option(self):
		name = make_employee("ac.self@example.com", COMPANY)
		frappe.db.set_value("Employee", name, "auto_checkin", 0)  # a test run before may have left it on
		user = frappe.db.get_value("Employee", name, "user_id")
		frappe.get_doc("User", user).remove_roles("HR Manager", "HR User", "System Manager")
		frappe.set_user(user)
		doc = frappe.get_doc("Employee", name)
		doc.auto_checkin = 1
		self.assertRaises(frappe.PermissionError, doc.save, ignore_permissions=True)
		frappe.set_user("Administrator")
		doc = frappe.get_doc("Employee", name)
		doc.auto_checkin = 1
		doc.save()
		self.assertEqual(frappe.db.get_value("Employee", name, "auto_checkin"), 1)
