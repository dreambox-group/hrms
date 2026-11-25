# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt
"""Drea access cleanup (owner, 25 Nov 2026): disable the roles of apps and modules Dreambox does
not use and replace ERPNext's sample role profiles with a Staff profile. It also disables website
users that never logged in, unless they are Drea Finance users.

Dry run first; it prints every change and saves nothing:

    bench --site <site> execute hrms.hr.drea_access_setup.apply
    bench --site <site> execute hrms.hr.drea_access_setup.apply --kwargs "{'dry_run': False}"

Disabled, never deleted: a disabled role is hidden everywhere and can be enabled again. A role
someone still holds is left alone and reported.
"""

import frappe

DISABLED_ROLES = (
	# Helpdesk (its two customer roles sent Administrator to a missing /helpdesk page)
	"HD Customer", "HD Customer Manager", "Agent", "Agent Manager",
	"Knowledge Base Contributor", "Knowledge Base Editor",
	# telephony
	"TP Agent", "TP Manager",
	# learning (LMS)
	"Academics User", "Batch Evaluator", "Course Creator", "Instructor", "LMS Student", "Moderator",
	# Insights
	"Insights Admin", "Insights User",
	# loans
	"Loan Appraiser", "Loan LOS User", "Loan Manager", "Loan Officer", "Loan Processor",
	"Loan Reporter", "Loan Underwriter",
	# selling, buying
	"Sales Manager", "Sales Master Manager", "Sales User", "Customer",
	"Purchase Manager", "Purchase Master Manager", "Purchase User", "Supplier",
	# stock, delivery, manufacturing
	"Stock Manager", "Stock User", "Item Manager", "Delivery Manager", "Delivery User",
	"Fulfillment User", "Manufacturing Manager", "Manufacturing User",
	# maintenance, quality
	"Maintenance Manager", "Maintenance User", "Quality Manager", "Fleet Manager",
	# website and misc (Script Manager is a Frappe standard role and cannot be disabled)
	"Website Manager", "Newsletter Manager", "Marketing Manager", "Support Team", "Translator", "Inbox User",
)  # fmt: skip

DELETED_ROLE_PROFILES = ("Purchase", "Sales", "Accounts", "Manufacturing", "Inventory")
ROLE_PROFILES = {"Staff": ["Employee"]}  # "HR" stays as HR set it


class Plan:
	def __init__(self, dry_run):
		self.dry_run = dry_run
		self.lines = []

	def do(self, message, action):
		self.lines.append(message)
		if not self.dry_run:
			action()


def apply(dry_run=True):
	dry_run = dry_run not in (False, 0, "0", "false", "False")
	plan = Plan(dry_run)

	held = dict(
		frappe.db.sql(
			"""select role, count(distinct parent) from "tabHas Role"
			where parenttype = 'User' and parent not in ('Administrator', 'Guest') group by role"""
		)
	)
	for role in DISABLED_ROLES:
		if not frappe.db.exists("Role", role) or frappe.db.get_value("Role", role, "disabled"):
			continue
		if held.get(role):
			print(f"   kept role {role!r}: {held[role]} user(s) hold it")
			continue
		plan.do(f"Disable role {role!r}", lambda r=role: disable_role(r))

	for profile in DELETED_ROLE_PROFILES:
		if not frappe.db.exists("Role Profile", profile):
			continue
		if frappe.db.exists("User", {"role_profile_name": profile}):
			print(f"   kept role profile {profile!r}: users have it")
			continue
		plan.do(
			f"Delete role profile {profile!r}",
			lambda p=profile: frappe.delete_doc("Role Profile", p, ignore_permissions=True),
		)
	for profile, roles in ROLE_PROFILES.items():
		if not frappe.db.exists("Role Profile", profile):
			plan.do(
				f"Create role profile {profile!r} ({', '.join(roles)})",
				lambda p=profile, r=roles: frappe.get_doc(
					{"doctype": "Role Profile", "role_profile": p, "roles": [{"role": x} for x in r]}
				).insert(ignore_permissions=True),
			)

	for user in idle_website_users():
		plan.do(f"Disable website user {user} (never logged in, no roles)", lambda u=user: disable_user(u))

	if not dry_run:
		frappe.db.commit()  # nosemgrep: a bench execute command, run by hand
		frappe.clear_cache()
	print(f"{'DRY RUN, nothing saved' if dry_run else 'APPLIED'}: {len(plan.lines)} change(s)")
	for line in plan.lines:
		print(" -", line)
	return plan.lines


def disable_role(role):
	doc = frappe.get_doc("Role", role)
	doc.disabled = 1
	doc.home_page = None  # the Helpdesk roles pointed at a page this site does not have
	doc.save(ignore_permissions=True)


def idle_website_users():
	"""Website users who never logged in, hold no role, are no employee's login and are no Drea
	Finance user. Drea Finance keeps its logins (staff, vendors, department heads, service accounts)
	in this same User table, as website users that never log in here: those stay untouched."""
	linked = set(frappe.get_all("Employee", filters={"user_id": ("is", "set")}, pluck="user_id"))
	if frappe.db.has_column("User", "drea_finance_role"):
		linked |= set(frappe.get_all("User", filters={"drea_finance_role": ("is", "set")}, pluck="name"))
	with_roles = set(
		frappe.get_all("Has Role", filters={"parenttype": "User", "role": ("not in", ["Guest", "All"])}, pluck="parent")
	)
	return [
		u.name
		for u in frappe.get_all(
			"User",
			filters={"user_type": "Website User", "enabled": 1, "name": ("not in", ["Guest", "Administrator"])},
			fields=["name", "last_login"],
			order_by="name",
		)
		if not u.last_login and u.name not in linked and u.name not in with_roles
	]


def disable_user(user):
	frappe.db.set_value("User", user, "enabled", 0)
