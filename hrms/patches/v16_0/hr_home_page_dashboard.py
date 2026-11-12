# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""HR lands on HR Dashboard after signing in (owner, 11 Nov 2026: "HR Dashboard will be Home").

Sets the Home Page of HR Manager and HR User to HR Dashboard where it is empty or one this app
set before (the old /hr-start, then HR Setup): a home page someone chose in the Role form stays."""

import frappe

HOME = "desk/hr-dashboard"
OURS = ("", "hr-start", "desk/hr-setup")


def execute():
	for role in ("HR Manager", "HR User"):
		if frappe.db.exists("Role", role) and (frappe.db.get_value("Role", role, "home_page") or "") in OURS:
			frappe.db.set_value("Role", role, "home_page", HOME)
	frappe.cache.delete_key("home_page")
