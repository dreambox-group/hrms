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

import frappe
from frappe import _

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
