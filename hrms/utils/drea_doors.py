# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Two addresses, one site (owner, 11 Nov 2026).

hris.dreambox.id is HR Setup, for HR only; one.dreambox.id is Drea One, for everyone. Both reach
this same site through the server's nginx, which sets X-Forwarded-Host to the address used.

- Signing in on the HR address (Frappe's sign-in, Drea One's, an email link, "Login as") is
  refused for anyone without an HR role, before any session is made (on_login).
- A session that already exists on the HR address for such a user is ended on its next request
  (before_request), so an old cookie does not keep them in.
- One address is the HR one only when the site says so in site_config: drea_hr_host
  ("hris.dreambox.id"); drea_staff_host ("one.dreambox.id") is named in the refusal. Without
  drea_hr_host, or on a request that does not carry X-Forwarded-Host, nothing is refused, so a
  missing header can never lock staff out of Drea One.

nginx does the rest: on the HR address /hr and the password links go to one.dreambox.id; on
one.dreambox.id the desk goes to hris.dreambox.id.
"""

import frappe
from frappe import _

HR_ROLES = {"HR Manager", "HR User", "System Manager"}


def _host(value: str | None) -> str:
	return (value or "").split(",")[0].strip().lower().split(":")[0]


def hr_host() -> str:
	return _host(frappe.conf.get("drea_hr_host"))


def staff_host() -> str:
	return _host(frappe.conf.get("drea_staff_host")) or "one.dreambox.id"


def on_hr_address() -> bool:
	"""True only when this request came in on the HR address, as nginx labels it."""
	wanted = hr_host()
	if not wanted or not getattr(frappe.local, "request", None):
		return False
	return _host(frappe.get_request_header("X-Forwarded-Host")) == wanted


def is_hr(user: str | None) -> bool:
	if not user or user == "Guest":
		return False
	return user == "Administrator" or bool(HR_ROLES & set(frappe.get_roles(user)))


def refusal_message() -> str:
	return _("{0} is for HR only. Please sign in at {1}.").format(hr_host(), staff_host())


def refuse_non_hr_sign_in(login_manager):
	"""on_login: before any session exists, so nothing is left behind. Guest is never refused:
	signing out (and an expired cookie) "signs in" as Guest, which must reach the sign-in page."""
	if login_manager.user in (None, "", "Guest"):
		return
	if on_hr_address() and not is_hr(login_manager.user):
		frappe.throw(refusal_message(), frappe.AuthenticationError, title=_("Not for this address"))


def end_non_hr_session():
	"""before_request: a session made before the rule (or on the other address and carried over by
	hand) ends on the HR address; the person is told where to go."""
	user = getattr(frappe.session, "user", None)
	if not user or user == "Guest" or not on_hr_address() or is_hr(user):
		return
	frappe.local.login_manager.logout()
	frappe.throw(refusal_message(), frappe.AuthenticationError, title=_("Not for this address"))
