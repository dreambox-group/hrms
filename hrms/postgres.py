# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Make Postgres behave like MariaDB where the code relies on it.

Frappe does the same for DECIMAL (DEC2FLOAT in frappe/database/postgres/database.py) and patches
pypika's ValueWrapper itself (frappe/query_builder/terms.py). Everything here also holds on
MariaDB, so it changes nothing there.

- TIME: MariaDB gives a timedelta, psycopg2 a datetime.time; shift code adds them to datetimes.
- JSON: MariaDB gives the text, psycopg2 the parsed value; Frappe's own DocType validation
  json.loads link_filters, which fails on a list.
- True/False going in: MariaDB takes them as 1/0, Postgres refuses a boolean in a Check
  (smallint) column. Frappe's Postgres schema has no boolean columns. Query builder values
  other than strings are written into the SQL by pypika, not passed as parameters, so both
  paths are covered.
"""

from datetime import timedelta

from pypika.terms import ValueWrapper

try:
	import psycopg2.extensions
except ImportError:  # no Postgres driver, so nothing to adapt
	psycopg2 = None


def time_to_timedelta(value, cursor):
	if value is None:
		return None
	clock = value.split("+")[0].split("-")[0]  # time with time zone ends in +07 or -03
	hours, minutes, seconds = clock.split(":")
	return timedelta(hours=int(hours), minutes=int(minutes), seconds=float(seconds))


def keep_text(value, cursor):
	return value


_get_formatted_value = ValueWrapper.get_formatted_value.__func__


def get_formatted_value(cls, value, **kwargs):
	if isinstance(value, bool):
		return "1" if value else "0"
	return _get_formatted_value(cls, value, **kwargs)


def register():
	ValueWrapper.get_formatted_value = classmethod(get_formatted_value)
	if not psycopg2:
		return
	psycopg2.extensions.register_type(
		psycopg2.extensions.new_type(psycopg2.extensions.TIME.values, "TIME_AS_TIMEDELTA", time_to_timedelta)
	)
	psycopg2.extensions.register_type(psycopg2.extensions.new_type((114, 3802), "JSON_AS_TEXT", keep_text))
	psycopg2.extensions.register_adapter(bool, lambda value: psycopg2.extensions.AsIs(int(value)))
