# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""HR lands on /hr-start after signing in (owner, 10 Nov 2026): two buttons, HR Setup and Drea One.

Sets the Home Page of the roles HR Manager and HR User, only where it is still empty: a home page
someone has chosen in the Role form stays. Runs once per site; to undo, clear the field there."""

import frappe

HOME = "hr-start"


def execute():
	for role in ("HR Manager", "HR User"):
		if frappe.db.exists("Role", role) and not frappe.db.get_value("Role", role, "home_page"):
			frappe.db.set_value("Role", role, "home_page", HOME)
	frappe.cache.delete_key("home_page")
