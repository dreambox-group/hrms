import frappe
from frappe.boot import load_translations

no_cache = 1


def get_context(context):
	redirect_desk_user_without_employee()
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosempgrep
	context = frappe._dict()
	context.csrf_token = csrf_token
	context.boot = get_boot()
	context.site_name = frappe.local.site
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return get_boot()


def get_boot():
	bootinfo = frappe._dict(
		{
			"site_name": frappe.local.site,
			"socketio_port": frappe.conf.get("socketio_port") or 9000,
			"push_relay_server_url": frappe.conf.get("push_relay_server_url") or "",
			"default_route": get_default_route(),
		}
	)

	bootinfo.lang = frappe.local.lang
	load_translations(bootinfo)

	return bootinfo


def get_default_route():
	path = frappe.request.path if frappe.request else ""
	return "/hr" if path == "/hr" or path.startswith("/hr/") else "/hrms"


HR_DESK_ROUTE = "/desk/hr-setup"


def redirect_desk_user_without_employee():
	"""Drea One is for employees. Since Drea One became the site's default app, a desk account with no
	employee record (Administrator, an HR or Finance admin) lands here after sign-in and the app can
	only show "no active employee found" and sign them out again. Send such accounts to the desk
	instead: the HR desk for HR staff and admins (the desk's "Frappe HR" tile also points here), the
	plain desk for anyone else. Guests see the login page as before; a website user without an employee still gets
	the app's own message."""
	user = frappe.session.user
	if not user or user == "Guest":
		return
	if frappe.db.exists("Employee", {"user_id": user, "status": "Active"}):
		return
	if frappe.db.get_value("User", user, "user_type") != "System User":
		return
	# HR staff and admins come here from the desk's "Frappe HR" tile: open the HR desk, not the app list
	hr_desk = {"HR Manager", "HR User", "System Manager"} & set(frappe.get_roles(user))
	frappe.local.flags.redirect_location = HR_DESK_ROUTE if hr_desk else "/desk"
	raise frappe.Redirect
