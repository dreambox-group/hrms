# Copyright (c) 2026, Dreambox and contributors
# For license information, please see license.txt

"""Was: HR lands on /hr-start (10 Nov 2026). That page is gone (11 Nov 2026); on a new site this
patch now does what hr_home_page_desk does, so the two never disagree."""

from hrms.patches.v16_0.hr_home_page_desk import execute  # noqa: F401
