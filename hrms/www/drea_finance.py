# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""/drea-finance (template drea-finance.html; Frappe maps the hyphen to this underscore module): the desk's way into Drea Finance (handbook 7.6).

The apps-screen entry points here, and this page sends the browser on to the Finance URL kept in
HR Settings. Keeping the URL in settings means the icon works the moment the URL is saved."""

import frappe
from frappe import _

from hrms.finance import get_finance_url, has_finance_access

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in first."), frappe.PermissionError)
	url = get_finance_url()
	if not url or not has_finance_access():
		frappe.throw(_("You don't have access to Drea Finance. Ask a Finance admin."), frappe.PermissionError)
	frappe.local.flags.redirect_location = url
	raise frappe.Redirect
