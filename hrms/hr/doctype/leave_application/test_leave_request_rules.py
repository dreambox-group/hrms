# Copyright (c) 2026, Dreambox and contributors
# See license.txt

import base64

import frappe
from frappe.utils import add_days, get_year_ending, get_year_start, getdate, nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.api.home import get_home_data
from hrms.hr.doctype.leave_application.leave_application import (
	LeaveRequestLockedError,
	decide_leave_application,
)
from hrms.hr.doctype.leave_application.leave_documents import (
	get_missing_documents,
	remind_missing_leave_documents,
	upload_leave_document,
)
from hrms.hr.doctype.leave_application.test_leave_application import make_allocation_record
from hrms.hr.utils import get_holiday_dates_for_employee
from hrms.tests.utils import HRMSTestSuite, make_user

COMPANY = "_Test Company"
STAFF = "lr.staff@example.com"
APPROVER = "lr.approver@example.com"
OTHER = "lr.other@example.com"
HR = "lr.hr@example.com"
SICK = "_Test LR Sick Leave"


def make_photo():
	import io

	from PIL import Image

	content = io.BytesIO()
	Image.new("RGB", (40, 30), "white").save(content, format="PNG")
	return "data:image/png;base64," + base64.b64encode(content.getvalue()).decode()


PHOTO = make_photo()


class TestLeaveRequestRules(HRMSTestSuite):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.set_single_value("HR Settings", "leave_approval_by_levels", 0)
		for user, role in ((APPROVER, "Leave Approver"), (OTHER, "Leave Approver"), (HR, "HR User")):
			make_user(user, role)
		self.employee = make_employee(STAFF, COMPANY)
		make_employee(APPROVER, COMPANY)
		if not frappe.db.exists("Leave Type", SICK):
			frappe.get_doc(
				{
					"doctype": "Leave Type",
					"leave_type_name": SICK,
					"requires_supporting_document": 1,
					"document_grace_days": 7,
				}
			).insert()
		clear_leave(self.employee)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_approver_decides_with_one_tap(self):
		application = apply_for_leave(self.employee)

		self.assertRaises(
			frappe.PermissionError, as_user, OTHER, decide_leave_application, application.name, "Approved"
		)
		self.assertEqual(
			as_user(APPROVER, decide_leave_application, application.name, "Approved"), "Approved"
		)

		application.reload()
		self.assertEqual((application.status, application.docstatus), ("Approved", 1))

	def test_hr_can_decide_too(self):
		application = apply_for_leave(self.employee)
		self.assertEqual(as_user(HR, decide_leave_application, application.name, "Rejected"), "Rejected")

	def test_sent_request_cannot_be_changed(self):
		application = apply_for_leave(self.employee)

		for user, field, value in (
			(STAFF, "description", "changed my mind"),
			(STAFF, "to_date", add_days(application.to_date, 1)),
			(APPROVER, "status", "Approved"),
		):
			frappe.set_user(user)
			doc = frappe.get_doc("Leave Application", application.name)
			doc.set(field, value)
			self.assertRaises(LeaveRequestLockedError, doc.save, ignore_permissions=False)
			frappe.set_user("Administrator")

		# HR can still correct it
		frappe.set_user(HR)
		doc = frappe.get_doc("Leave Application", application.name)
		doc.description = "corrected by HR"
		doc.save()

	def test_document_can_follow_the_request(self):
		application = apply_for_leave(self.employee, SICK)
		self.assertEqual(
			getdate(application.document_due_date), getdate(add_days(application.posting_date, 7))
		)
		self.assertIn(application.name, [a.name for a in get_missing_documents()])

		# approved without the document, still reminded
		as_user(APPROVER, decide_leave_application, application.name, "Approved")
		self.assertIn(
			application.name, [a.name for a in as_user(STAFF, get_home_data)["missing_documents"]["mine"]]
		)
		self.assertIn(
			application.name,
			[a.name for a in as_user(APPROVER, get_home_data)["missing_documents"]["to_review"]],
		)
		remind_missing_leave_documents()
		self.assertTrue(
			frappe.db.exists(
				"PWA Notification", {"to_user": STAFF, "reference_document_name": application.name}
			)
		)

		# only the employee (or HR) uploads it, also after approval
		self.assertRaises(
			frappe.PermissionError,
			as_user,
			APPROVER,
			upload_leave_document,
			application.name,
			"note.png",
			PHOTO,
		)
		as_user(STAFF, upload_leave_document, application.name, "note.png", PHOTO)
		self.assertNotIn(application.name, [a.name for a in get_missing_documents()])

	def test_only_photos_and_pdfs(self):
		application = apply_for_leave(self.employee, SICK)
		script = "data:text/html;base64," + base64.b64encode(b"<script>").decode()
		self.assertRaises(
			frappe.ValidationError, as_user, STAFF, upload_leave_document, application.name, "x.html", script
		)

	def test_no_due_date_without_the_setting(self):
		application = apply_for_leave(self.employee)
		self.assertFalse(application.document_due_date)


def as_user(user, fn, *args):
	frappe.set_user(user)
	try:
		return fn(*args)
	finally:
		frappe.set_user("Administrator")


def clear_leave(employee):
	applications = frappe.get_all("Leave Application", filters={"employee": employee}, pluck="name")
	if applications:
		frappe.db.delete(
			"File", {"attached_to_doctype": "Leave Application", "attached_to_name": ("in", applications)}
		)
		frappe.db.delete("Leave Application", {"name": ("in", applications)})
	frappe.db.delete("Leave Ledger Entry", {"employee": employee, "transaction_type": "Leave Application"})


def apply_for_leave(employee, leave_type="_Test Leave Type"):
	date = add_days(getdate(), 10)
	holidays = {str(d) for d in get_holiday_dates_for_employee(employee, date, get_year_ending(date))}
	while str(date) in holidays or date.weekday() >= 5:
		date = add_days(date, 1)
	if not frappe.db.exists(
		"Leave Allocation",
		{"employee": employee, "leave_type": leave_type, "docstatus": 1, "to_date": (">=", date)},
	):
		make_allocation_record(
			employee, leave_type, from_date=get_year_start(date), to_date=get_year_ending(date)
		)

	frappe.set_user(STAFF)
	try:
		return frappe.get_doc(
			{
				"doctype": "Leave Application",
				"employee": employee,
				"leave_type": leave_type,
				"from_date": date,
				"to_date": date,
				"company": COMPANY,
				"posting_date": nowdate(),
				"leave_approver": APPROVER,
			}
		).insert()
	finally:
		frappe.set_user("Administrator")
