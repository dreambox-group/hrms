# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Keep the HR desk quick to open (owner, 11 Nov 2026: "lag and long loading").

The database is on Neon in Singapore, about 15 ms away, and a desk's first load builds per-user
caches that Frappe keeps for 6 hours (and drops on every clear-cache): which dashboards, pages and
reports the user may see. For an HR account that is some 4,000 queries, about 70 seconds. This
builds those caches in the background, so a person never waits for it.

Nothing is stored that Frappe would not store by itself: it runs the desk's own boot as each HR
account, which fills Frappe's caches (permissions, dashboards, pages, reports, metadata), and
throws the boot away; the person's own boot is then built from those caches when they open the
desk, in a second or so.

- Every hour (scheduler, hourly_long): only accounts whose caches have gone.
- After a deploy or clear-cache:  bench --site <site> execute hrms.utils.warm_desk.warm_hr_desks
"""

import time

import frappe

DESK_ROLES = ("HR Manager", "HR User", "System Manager")


def desk_users() -> list[str]:
	users = set(
		frappe.get_all("Has Role", filters={"role": ["in", DESK_ROLES], "parenttype": "User"}, pluck="parent")
	)
	users.discard("Guest")
	users.discard("Administrator")
	enabled = frappe.get_all(
		"User", filters={"name": ["in", list(users) or [""]], "enabled": 1, "user_type": "System User"}, pluck="name"
	)
	return sorted(enabled)


def is_warm(user: str) -> bool:
	return frappe.cache.get_value("allowed_dashboards", user=user) is not None


def warm_hr_desks(only_cold: bool = False) -> list[tuple[str, str, float]]:
	"""Build each HR account's desk caches. Returns (user, "built" | "warm" | "failed: …", seconds)."""
	from frappe.boot import get_bootinfo

	me = frappe.session.user
	done = []
	try:
		for user in desk_users():
			if only_cold and is_warm(user):
				done.append((user, "warm", 0.0))
				continue
			started = time.monotonic()
			try:
				frappe.set_user(user)
				get_bootinfo()  # fills the caches; the boot itself is not kept
				done.append((user, "built", round(time.monotonic() - started, 1)))
			except Exception as e:
				done.append((user, f"failed: {type(e).__name__}", round(time.monotonic() - started, 1)))
				frappe.log_error("Warm HR desk", reference_doctype="User", reference_name=user)
			finally:
				frappe.db.rollback()  # the boot writes nothing; make sure of it
	finally:
		frappe.set_user(me)
	for user, what, seconds in done:
		print(f"{user}: {what} ({seconds} s)")
	return done


def warm_cold_hr_desks():
	"""scheduler_events hourly_long: only the accounts whose caches have expired."""
	warm_hr_desks(only_cold=True)
