# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""/hr-start (template hr-start.html): where HR lands after signing in (owner, 10 Nov 2026).

Two buttons: "HR Setup" (the HR desk: employees, users, leave, payroll) and "Drea One" (the
employee app). Roles HR Manager and HR User get this page as their Home Page (patch
hr_start_home_page), so HR chooses where to go instead of being dropped in the desk. Anyone else
who opens it goes straight on to Drea One; guests are sent to sign in first."""

from urllib.parse import urlencode

import frappe

from hrms.www.hrms import HR_DESK_ROUTE

no_cache = 1

HR_ROLES = {"HR Manager", "HR User", "System Manager"}


def get_context(context):
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.local.flags.redirect_location = "/login?" + urlencode({"redirect-to": "/hr-start"})
		raise frappe.Redirect
	if not HR_ROLES & set(frappe.get_roles(user)):
		frappe.local.flags.redirect_location = "/hr"
		raise frappe.Redirect

	context.no_header = 1
	context.no_breadcrumbs = 1
	context.full_name = frappe.db.get_value("User", user, "first_name") or user
	context.desk_url = HR_DESK_ROUTE
	context.one_url = "/hr"
	context.has_employee = bool(frappe.db.exists("Employee", {"user_id": user, "status": "Active"}))
	return context
