# Copyright (c) 2026, Dreambox and contributors
# See license.txt

from datetime import datetime

import frappe
from frappe.utils import get_time, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api.hr_dashboard import get_dashboard_data
from hrms.hr.doctype.employee_checkin.employee_checkin import CheckinRadiusExceededError
from hrms.hr.doctype.employee_checkin.test_employee_checkin import make_shift_location
from hrms.hr.doctype.leave_application.test_leave_approval_levels import make_department
from hrms.hr.doctype.shift_type.test_shift_type import make_shift_assignment, setup_shift_type
from hrms.hr.office_range import get_outside_office_checkins, get_outside_office_for_supervisor
from hrms.tests.utils import HRMSTestSuite

COMPANY = "_Test Company"
HEAD = "or.head@example.com"
LEAD = "or.lead@example.com"
OTHER = "or.other@example.com"


class TestOfficeRange(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 1)
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 1)
		self.department = make_department("_Test OR Office", approvers=[(HEAD, "Required"), (LEAD, "Regular")])
		make_department("_Test OR Elsewhere", approvers=[(OTHER, "Required")])
		self.employee = make_employee("or.staff@example.com", COMPANY, department=self.department)
		frappe.db.delete("Employee Checkin", {"employee": self.employee})
		frappe.db.delete("Shift Assignment", {"employee": self.employee})
		self.shift = setup_shift_type(shift_type="_Test OR Office Shift", start_time="08:00:00", end_time="17:00:00")
		self.office = frappe.db.get_value("Shift Location", "_Test OR Office") or make_shift_location(
			"_Test OR Office", 24, 72
		).name
		make_shift_assignment(self.shift.name, self.employee, getdate(), shift_location=self.office)
		self.time = datetime.combine(getdate(), get_time("10:00:00"))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "allow_geolocation_tracking", 0)
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)

	def checkin(self, latitude, longitude, reason=None, minute=0):
		return frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"time": self.time.replace(minute=minute),
				"log_type": "IN",
				"latitude": latitude,
				"longitude": longitude,
				"outside_office_reason": reason,
			}
		).insert()

	def test_inside_the_radius(self):
		log = self.checkin(24.001, 72.001, reason="Meeting di Luar")
		self.assertFalse(log.outside_office_range)
		self.assertLess(log.office_distance, 500)
		# no reason is kept when it wasn't needed
		self.assertFalse(log.outside_office_reason)

	def test_outside_needs_a_reason(self):
		self.assertRaises(CheckinRadiusExceededError, self.checkin, 24.01, 72.01)
		log = self.checkin(24.01, 72.01, reason="Sudah izin Supervisor", minute=5)
		self.assertTrue(log.outside_office_range)
		self.assertGreater(log.office_distance, 1000)
		self.assertEqual(log.outside_office_reason, "Sudah izin Supervisor")

	def test_supervisors_and_hr_see_it_that_day(self):
		log = self.checkin(24.01, 72.01, reason="Meeting di Luar")
		for supervisor in (HEAD, LEAD):
			rows = get_outside_office_for_supervisor(supervisor, getdate())
			self.assertEqual([r.name for r in rows], [log.name])
			self.assertEqual(rows[0].location, self.office)
			self.assertEqual(rows[0].outside_office_reason, "Meeting di Luar")
		self.assertEqual(get_outside_office_for_supervisor(OTHER, getdate()), [])

		self.assertIn(log.name, [r.name for r in get_outside_office_checkins(getdate())])
		self.assertIn(log.name, [r.name for r in get_dashboard_data()["outside_office"]])
		self.assertEqual(get_outside_office_checkins(frappe.utils.add_days(getdate(), -1), [self.employee]), [])

	def test_radius_is_at_most_500_m(self):
		location = frappe.get_doc("Shift Location", self.office)
		location.checkin_radius = 501
		self.assertRaises(frappe.ValidationError, location.save)
		self.assertEqual(
			frappe.get_meta("Shift Location").get_field("checkin_radius").default, "500"
		)

	def test_office_without_coordinates_is_not_checked(self):
		frappe.db.set_value("Shift Location", self.office, {"latitude": 0, "longitude": 0})
		try:
			log = self.checkin(24.01, 72.01)
			self.assertFalse(log.outside_office_range)
		finally:
			frappe.db.set_value("Shift Location", self.office, {"latitude": 24, "longitude": 72})
