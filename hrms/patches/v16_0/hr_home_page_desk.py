# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""HR lands in HR Setup after signing in (owner, 11 Nov 2026): the two-button page /hr-start is
gone; hris.dreambox.id is HR Setup and one.dreambox.id is Drea One.

Sets the Home Page of the roles HR Manager and HR User to the HR Setup page where it is empty or
still the old "hr-start": a home page someone chose in the Role form stays."""

import frappe

HOME = "desk/hr-setup"


def execute():
	for role in ("HR Manager", "HR User"):
		if frappe.db.exists("Role", role) and (frappe.db.get_value("Role", role, "home_page") or "") in ("", "hr-start"):
			frappe.db.set_value("Role", role, "home_page", HOME)
	frappe.cache.delete_key("home_page")
