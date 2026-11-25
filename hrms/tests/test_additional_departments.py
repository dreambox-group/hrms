# Copyright (c) 2026, Dreambox and contributors
# See license.txt
"""Employee > Secondary Departments: the leave approver of a person's secondary department sees them in
their Drea One team; the main department's approver still does; nobody else does."""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.supervisors import get_team

COMPANY = "_Test Company"


def make_department(name, approver):
	full = f"{name} - {frappe.get_cached_value('Company', COMPANY, 'abbr')}"
	if not frappe.db.exists("Department", full):
		frappe.get_doc({"doctype": "Department", "department_name": name, "company": COMPANY}).insert()
	doc = frappe.get_doc("Department", full)
	if approver not in [row.approver for row in doc.leave_approvers]:
		doc.append("leave_approvers", {"approver": approver})
		doc.save()
	return full


def make_user(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}).insert()
	return email


class TestAdditionalDepartments(IntegrationTestCase):
	def test_leaders_of_both_departments_see_the_person(self):
		main_lead = make_user("ad.main.lead@example.com")
		also_lead = make_user("ad.also.lead@example.com")
		other_lead = make_user("ad.other.lead@example.com")
		main = make_department("AD Main", main_lead)
		also = make_department("AD Also", also_lead)
		make_department("AD Other", other_lead)

		employee = make_employee("ad.person@example.com", company=COMPANY, department=main)
		doc = frappe.get_doc("Employee", employee)
		doc.set("additional_departments", [{"department": also}])
		doc.save()

		self.assertIn(employee, {e.name for e in get_team(main_lead)})
		self.assertIn(employee, {e.name for e in get_team(also_lead)})
		self.assertNotIn(employee, {e.name for e in get_team(other_lead)})
		# listed once even when both departments are the same leader's
		make_department("AD Also", main_lead)
		self.assertEqual([e.name for e in get_team(main_lead)].count(employee), 1)

	def test_a_relieved_person_is_not_in_the_team(self):
		lead = make_user("ad.lead2@example.com")
		also = make_department("AD Also 2", lead)
		employee = make_employee("ad.left@example.com", company=COMPANY)
		doc = frappe.get_doc("Employee", employee)
		doc.set("additional_departments", [{"department": also}])
		doc.save()
		self.assertIn(employee, {e.name for e in get_team(lead)})
		frappe.db.set_value("Employee", employee, {"status": "Left", "relieving_date": frappe.utils.today()})
		self.assertNotIn(employee, {e.name for e in get_team(lead)})
