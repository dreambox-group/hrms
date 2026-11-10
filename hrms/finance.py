# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Drea Finance in the same database as Frappe (decision of 2 Nov 2026).

Finance reads tabUser, tabCompany and tabDivision directly and keeps its own tables keyed by
their names, with foreign keys. What Frappe owes Finance:

- the Finance fields on User, Company and Department (hrms.setup.get_drea_finance_custom_fields);
- a way into Drea Finance from the desk (the apps-screen entry, route /drea-finance);
- a plain refusal before Postgres's own when someone deletes a user, company or division that
  Finance's books still point at (refuse_delete).

Frappe never writes to Finance's tables and never names them: the delete guard reads the
foreign keys from the database catalog, so Finance can add tables without touching this app.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint

FINANCE_ROLES = ("admin", "staff", "finance", "director", "dept_head", "vendor")
FINANCE_ADMIN_ROLE = "Finance Admin"


def get_finance_url() -> str | None:
	url = frappe.db.get_single_value("HR Settings", "drea_finance_url")
	return url.rstrip("/") if url else None


def has_finance_access(user: str | None = None) -> bool:
	"""Apps-screen permission for the Drea Finance entry: a Finance URL is set and the user has a Finance role."""
	user = user or frappe.session.user
	if user in ("Guest", None):
		return False
	if not get_finance_url():
		return False
	if not frappe.db.has_column("User", "drea_finance_role"):
		return False
	role, active = frappe.db.get_value("User", user, ["drea_finance_role", "drea_finance_active"]) or (
		None,
		0,
	)
	return bool(role) and bool(active)


# --- delete guard (handbook 7.7) --------------------------------------------------------------


def referencing_foreign_keys(doctype: str) -> list[tuple[str, str]]:
	"""(table, column) pairs of every foreign key in this database that points at tab<doctype>.name.

	Frappe itself creates no foreign keys, so these are Finance's. Postgres only; on MariaDB
	there is nothing to read and the list is empty."""
	if frappe.db.db_type != "postgres":
		return []
	rows = frappe.db.sql(
		"""
		select c.conrelid::regclass::text, a.attname
		from pg_constraint c
		join pg_attribute a on a.attrelid = c.conrelid and a.attnum = any(c.conkey)
		where c.contype = 'f' and c.confrelid = to_regclass(%s)
		""",
		(f'"tab{doctype}"',),
	)
	return [(table, column) for table, column in rows]


def finance_tables_using(doctype: str, name: str) -> list[str]:
	"""Names of the tables whose rows still point at this record."""
	using = []
	for table, column in referencing_foreign_keys(doctype):
		column = column.replace('"', '""')
		if frappe.db.sql(f'select 1 from {table} where "{column}" = %s limit 1', (name,)):
			using.append(table)
	return using


def refuse_delete(doc, method=None):
	"""on_trash for User, Company and Division: the foreign keys would refuse the delete anyway,
	but HR would see a raw database error. Say it plainly first."""
	using = finance_tables_using(doc.doctype, doc.name)
	if using:
		frappe.throw(
			_("Drea Finance's books use {0} ({1}). Disable it instead of deleting it.").format(
				frappe.bold(doc.name), ", ".join(sorted(using))
			),
			title=_("Used by Drea Finance"),
		)


# --- Department -> Division ---------------------------------------------------------------------


def validate_department_division(doc, method=None):
	"""A Department may only point at an active Division."""
	division = doc.get("drea_finance_division")
	if not division:
		return
	if not frappe.db.get_value("Division", division, "is_active"):
		frappe.throw(
			_("Division {0} is not active in Drea Finance. Pick an active division.").format(
				frappe.bold(division)
			)
		)


# --- User ---------------------------------------------------------------------------------------


def validate_user_finance_fields(doc, method=None):
	"""Keep the Finance fields consistent: a role from Finance's list, and divisions only with a role."""
	role = doc.get("drea_finance_role")
	if role and role not in FINANCE_ROLES:
		frappe.throw(_("Drea Finance Role must be one of: {0}").format(", ".join(FINANCE_ROLES)))
	if not role and doc.get("drea_finance_divisions"):
		frappe.throw(_("Give the user a Drea Finance Role before assigning divisions."))


# --- checks Drea Finance made in its own admin screens (Finance audit H2, 9 Nov 2026) -------------
#
# Editing people and companies moved to this desk on 4 Nov 2026; these are the refusals Finance's
# user and company screens made, so the desk makes them now. The two that read Finance's tables
# run only where those tables are in this database (Postgres, from the cutover) and are skipped,
# never fatal, if a table is missing or a query fails: a Finance change must not block HR's saves.


def finance_sql(query: str, values: tuple, tables: tuple[str, ...]):
	"""Run a read on Finance's tables, or return None when it cannot run here."""
	if frappe.db.db_type != "postgres":
		return None
	frappe.db.savepoint("drea_finance_check")
	try:
		# Inside the savepoint too: without read access to schema finance even the lookup fails.
		for table in tables:
			if not frappe.db.sql("select to_regclass(%s)", (f"finance.{table}",))[0][0]:
				frappe.db.release_savepoint("drea_finance_check")
				return None
		rows = frappe.db.sql(query, values)
	except Exception:
		# A failed statement spoils a Postgres transaction: undo it, note it, let the save go on.
		frappe.db.rollback(save_point="drea_finance_check")
		frappe.log_error("Drea Finance check skipped", reference_doctype="HR Settings")
		return None
	frappe.db.release_savepoint("drea_finance_check")
	return rows


def finance_on(enabled, active, role) -> bool:
	"""What Finance's trigger reads: enabled, the Finance switch on, and a Finance role."""
	return bool(cint(enabled) and cint(active) and (role or "").strip() in FINANCE_ROLES)


def rupiah(amount: float) -> str:
	return "Rp " + f"{round(amount):,}".replace(",", ".")


def validate_user_finance_guards(doc, method=None):
	"""User.validate: never leave Drea Finance without an active admin, and never switch off (or
	make finance, admin or vendor, who may not hold an advance) someone holding cash-advance money."""
	before = doc.get_doc_before_save()
	if not before or not frappe.db.has_column("User", "drea_finance_role"):
		return
	role_before = (before.get("drea_finance_role") or "").strip()
	role_now = (doc.get("drea_finance_role") or "").strip()
	on_before = finance_on(before.enabled, before.get("drea_finance_active"), role_before)
	on_now = finance_on(doc.enabled, doc.get("drea_finance_active"), role_now)

	if on_before and role_before == "admin" and not (on_now and role_now == "admin"):
		others = [
			name
			for name in frappe.get_all(
				"User",
				filters={
					"name": ["!=", doc.name],
					"enabled": 1,
					"drea_finance_role": "admin",
					"drea_finance_active": 1,
				},
				pluck="name",
			)
			if not never_gets_password(name)
		]
		if not others:
			frappe.throw(
				_("{0} is the last active Drea Finance admin. Make someone else admin first.").format(
					frappe.bold(doc.name)
				),
				title=_("Drea Finance needs an admin"),
			)

	leaves_wallet = on_before and (
		not on_now or (role_now != role_before and role_now in ("finance", "admin", "vendor"))
	)
	if leaves_wallet:
		rows = finance_sql(
			"""
			select coalesce(sum(w.amount), 0)
			from finance.wallet_entries w join finance.users u on u.id = w.holder_id
			where u.frappe_user = %s
			""",
			(doc.name,),
			("wallet_entries", "users"),
		)
		held = round(float(rows[0][0])) if rows else 0
		if held:
			frappe.throw(
				_(
					"{0} is holding {1} of cash advance. Record the return in Drea Finance (Cash advances, "
					"Monthly review) first."
				).format(frappe.bold(doc.full_name or doc.name), rupiah(held)),
				title=_("Cash advance still held"),
			)


def validate_company_finance_fields(doc, method=None):
	"""Company.validate: the withholding rate as Finance's company screen checked it, and no
	switching off a company whose bank accounts are still on in Drea Finance."""
	if not frappe.db.has_column("Company", "drea_finance_active"):
		return
	before = doc.get_doc_before_save()
	validate_company_finance_code(doc, before)
	percent = doc.get("withholding_tax_percent")
	if percent is not None and percent != "":
		percent = float(percent)
		if percent < 0 or percent > 100:
			frappe.throw(_("The withholding rate is a percent between 0 and 100."))
		if percent > 0 and not doc.get("withholding_kind"):
			frappe.throw(_("Say which tax the clients withhold: PPh 23 or PPh Final."))

	if before and cint(before.get("drea_finance_active")) and not cint(doc.get("drea_finance_active")):
		rows = finance_sql(
			"""
			select count(*)
			from finance.legal_entity_accounts a join finance.legal_entities e on e.id = a.legal_entity_id
			where e.company = %s and a.is_active
			""",
			(doc.name,),
			("legal_entity_accounts", "legal_entities"),
		)
		if rows and rows[0][0]:
			frappe.throw(
				_(
					"{0} still has {1} bank account(s) switched on in Drea Finance. Switch them off "
					"there first: payments can still be recorded from them."
				).format(frappe.bold(doc.name), rows[0][0]),
				title=_("Bank accounts still on"),
			)


def validate_company_finance_code(doc, before):
	"""Second audit (9 Nov 2026): Finance files a company's books under its code, and the copy
	matches companies by code. So once Drea Finance has books under this company its code
	stays, and a code Finance files under another company is not given to this one. Before
	the cutover (no finance schema) and for a company Finance has nothing under, it is free."""
	code_before = ((before.get("drea_finance_code") if before else "") or "").strip()
	code_now = (doc.get("drea_finance_code") or "").strip()
	if code_now == code_before:
		return
	if code_before:
		rows = finance_sql(
			"select count(*) from finance.legal_entities where company = %s",
			(doc.name,),
			("legal_entities",),
		)
		if rows and rows[0][0]:
			frappe.throw(
				_(
					"The Drea Finance code of {0} stays {1}: Drea Finance files this company's books "
					"under it. Ask the Finance admin if it really must change."
				).format(frappe.bold(doc.name), frappe.bold(code_before)),
				title=_("Drea Finance code"),
			)
	if code_now:
		rows = finance_sql(
			"select company from finance.legal_entities where entity_code = %s and company is distinct from %s",
			(code_now, doc.name),
			("legal_entities",),
		)
		if rows:
			frappe.throw(
				_("{0} is already the Drea Finance code of {1}.").format(
					frappe.bold(code_now), frappe.bold(rows[0][0] or _("a company Drea Finance has"))
				),
				title=_("Drea Finance code"),
			)


# --- service accounts never get a password (owner, 9 Nov 2026; Finance audit F7) ------------------
#
# hr-system@, appsheet@ and ai.assistant@ stay enabled users (their Finance rows and authorship
# need them), and every @dreambox.id mailbox receives mail, so "Forgot password" would hand
# whoever reads it a password. The list is HR Settings > Drea Finance, editable by a System
# Manager; everyone else keeps Forgot password and the admin reset.

NO_PASSWORD_FIELD = "drea_finance_no_password_users"
NO_PASSWORD_DEFAULT = ("hr-system@dreambox.id", "appsheet@dreambox.id", "ai.assistant@dreambox.id")


def no_password_users() -> set[str]:
	"""The listed accounts, lower-case. Until the setting has ever been saved, the three defaults."""
	Singles = frappe.qb.DocType("Singles")
	rows = (
		frappe.qb.from_(Singles)
		.select(Singles.value)
		.where((Singles.doctype == "HR Settings") & (Singles.field == NO_PASSWORD_FIELD))
		.run()
	)
	text = rows[0][0] if rows else "\n".join(NO_PASSWORD_DEFAULT)
	return {part.strip().lower() for part in re.split(r"[\s,;]+", text or "") if part.strip()}


def never_gets_password(user: str | None, email: str | None = None) -> bool:
	listed = no_password_users()
	return any((value or "").strip().lower() in listed for value in (user, email))


def refuse_service_account_login(login_manager):
	"""on_login, before any session is made (second audit, 9 Nov 2026): the listed service
	accounts never sign in, whatever the way: a password set before the list existed, a login
	link by email, Google, or "Login as". Calls with an API key make no session and still work."""
	if never_gets_password(login_manager.user):
		frappe.throw(
			_("{0} is a service account and does not sign in (HR Settings, Drea Finance).").format(
				frappe.bold(login_manager.user)
			),
			frappe.AuthenticationError,
		)


def refusal(user: str):
	frappe.throw(
		_("{0} is a service account and never gets a password (HR Settings, Drea Finance).").format(
			frappe.bold(user)
		),
		title=_("No password for service accounts"),
	)


def refuse_service_account_password(doc, method=None):
	"""User.before_validate: the desk's "Set New Password" and change_password."""
	if doc.get("new_password") and never_gets_password(doc.name, doc.get("email")):
		refusal(doc.name)


def refuse_service_account_reset(doc, method=None):
	"""User.validate_reset_password: Forgot password and the desk's Reset Password. No link is made."""
	if never_gets_password(doc.name, doc.get("email")):
		refusal(doc.name)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_password(
	new_password: str, logout_all_sessions: int = 0, key: str | None = None, old_password: str | None = None
):
	"""/update-password, in place of Frappe's: a reset or welcome link made before the list (or by a
	path that skips the reset hook) still cannot set a service account's password."""
	from frappe.core.doctype.user.user import update_password as frappe_update_password
	from frappe.utils.data import sha256_hash

	user = None
	if key:
		user = frappe.db.get_value("User", {"reset_password_key": sha256_hash(key)}, "name")
	elif old_password:
		user = frappe.session.user
	if user and never_gets_password(user, frappe.db.get_value("User", user, "email")):
		refusal(user)
	return frappe_update_password(
		new_password=new_password, logout_all_sessions=logout_all_sessions, key=key, old_password=old_password
	)
