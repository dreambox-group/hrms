# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Dreambox logo on the sign-in page (owner, 11 Nov 2026). Frappe takes the sign-in page's logo
from Navbar Settings' "Application Logo" (or Website Settings' "App Logo"); with three apps'
logos in the hooks it would otherwise show the Frappe Framework logo. Set only where nobody has
chosen one; the favicon and loading screen come from hooks.website_context."""

import frappe

LOGO = "/assets/hrms/images/dreambox-logo.png"


def execute():
	if frappe.db.get_single_value("Website Settings", "app_logo"):
		return
	if not frappe.db.get_single_value("Navbar Settings", "app_logo"):
		frappe.db.set_single_value("Navbar Settings", "app_logo", LOGO)
	frappe.clear_cache()
