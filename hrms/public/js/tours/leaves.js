// Leaves tutorials (owner, 24 Nov 2026): requests, allocations, holidays, leave setup, reports.
// Engine: hr_tours.js.
(function () {
	const { step, top } = window.hrms_tours.h;
	const { list, form, report } = window.hrms_tours.builders;

	const L = {
		"Leave Application": list(__("Leave Applications"),
			__("Leave requests. Staff send them from Drea One; HR can enter one here for someone."), {
				rows: [__("Status"), __("<b>Open</b> while waiting, then <b>Approved</b> or <b>Rejected</b>. Switch to Calendar view (top) to see who is away when.")],
				filters: __("Filter by employee, leave type or status."),
				add: [__("Leave for someone"), __("Pick the person, the leave type and the dates; their approvers decide as usual.")],
			}),
		"Leave Allocation": list(__("Leave Allocations"),
			__("How many days of each leave type a person may take, and in which period. Requests are checked against it."), {
				add: [__("Give days"), __("One person, one leave type. For many people at once use <b>Leave Control Panel</b>.")],
			}),
		"Leave Policy Assignment": list(__("Leave Policy Assignments"),
			__("Gives a person every leave type of a Leave Policy at once, for a period."), {
				add: [__("Assign a policy"), __("Pick the person, the policy and the dates, then Submit: the allocations are made.")],
			}),
		"Holiday List": list(__("Holiday Lists"),
			__("Days off: weekends, public holidays and cuti bersama. Each company has a default; a person can have their own."), {
				add: [__("A new list"), __("Usually one per year: the year's dates, weekly offs, then Indonesia's public holidays.")],
			}),
		"Holiday List Assignment": list(__("Holiday List Assignments"),
			__("Which holiday list a company or a person follows from a date."), {
				add: [__("Assign a list"), __("Pick company or employee, the list and the start date, then Submit.")],
			}),
		"Leave Type": list(__("Leave Types"),
			__("The kinds of leave: annual (cuti tahunan), sick, unpaid, Cuti Pengganti… Each one's rules are in its form."), {
				add: [__("A new leave type"), __("Name it and set whether it is paid, counts holidays and can carry over.")],
			}),
		"Leave Policy": list(__("Leave Policies"), __("A set of leave types with the days of each, given together."), {
			add: [__("A new policy"), __("Name it, add each leave type and its days, then Submit.")],
		}),
		"Leave Period": list(__("Leave Periods"), __("The leave year per company, for example 1 Jan–31 Dec."), {
			add: [__("A new period"), __("The dates and the company; tick Is Active.")],
		}),
		"Leave Encashment": list(__("Leave Encashments"), __("Pays out unused leave days, through payroll."), {
			add: [__("Pay out leave"), __("The person, the leave type and the period; the days and amount are worked out.")],
		}),
		"Leave Block List": list(__("Leave Block Lists"),
			__("Days nobody may take leave (for example the year-end close), except the people allowed."), {
				add: [__("A new block list"), __("Name, company, the blocked days and who may still take leave.")],
			}),
		"Compensatory Leave Request": list(__("Overtime Submissions (Cuti Pengganti)"),
			__("Holidays an employee worked. Once their supervisors approve, they get the same number of days off. Staff send them from Drea One, Leaves, Overtime Submission."), {
				add: [__("Enter one"), __("The person, the holidays worked and why; their supervisors decide.")],
			}),
	};

	const F = {
		"Leave Application": form({
			fields: [
				["employee", __("Employee"), __("Who is taking leave.")],
				["leave_type", __("Leave Type"), __("Which leave: its rules decide paid or unpaid and whether holidays count.")],
				["from_date", __("Dates"), __("From and To. Tick <b>Half Day</b> for half a day.")],
				["total_leave_days", __("Total Leave Days"), __("Worked out from the dates; holidays are left out unless the leave type counts them.")],
				["leave_balance", __("Balance"), __("What they had before this request.")],
				["description", __("Reason"), __("Why; their approvers see it.")],
				["leave_approver", __("Approver"), __("Who decides. With approval by levels (HR Settings), all of the department's approvers are listed and decide.")],
				["status", __("Status"), __("Open while waiting. The approver sets Approved or Rejected, then Submit.")],
			],
			end: [__("After approval"), __("Approved leave is marked on attendance for those days. Unpaid leave lowers that month's pay.")],
		}),
		"Leave Allocation": form({
			fields: [
				["employee", __("Employee"), __("Who gets the days.")],
				["leave_type", __("Leave Type"), __("Which leave.")],
				["from_date", __("Period"), __("From and To: when the days can be used.")],
				["new_leaves_allocated", __("New Leaves Allocated"), __("The days given.")],
				["carry_forward", __("Carry forward"), __("Adds last period's unused days, if the leave type allows it.")],
			],
			end: [__("Submit"), __("Submit to make the days usable.")],
		}),
		"Leave Policy Assignment": form({
			fields: [
				["employee", __("Employee"), __("Who gets the policy.")],
				["leave_policy", __("Leave Policy"), __("The set of leave types and days.")],
				["effective_from", __("Effective dates"), __("From and To: the period the days are for.")],
			],
			end: [__("Submit"), __("Submit: one allocation per leave type of the policy is made.")],
		}),
		"Leave Control Panel": form({
			intro: [__("Leave Control Panel"), __("Gives leave to many people at once.")],
			fields: [
				["dates_based_on", __("Dates"), __("A Leave Period, or your own From and To.")],
				["allocate_based_on_leave_policy", __("Policy or leave type"), __("Ticked: give a Leave Policy. Unticked: one leave type and a number of days.")],
				["no_of_days", __("Days"), __("How many days of the leave type.")],
				["branch", __("Who"), __("Narrow the people with the filters: company, branch, department, employment type…")],
				["employees_html", __("Select and allocate"), __("Tick the people in the list, then <b>Allocate Leave</b>.")],
			],
		}),
		"Holiday List": form({
			fields: [
				["holiday_list_name", __("Name"), __("For example \"Dreambox 2027\".")],
				["from_date", __("Dates"), __("The year it covers.")],
				["weekly_off", __("Weekly off"), __("Pick Saturday, then <b>Add to Holidays</b>; again for Sunday.")],
				["country", __("Public holidays"), __("Pick Indonesia, then <b>Add to Holidays</b>.")],
				["holidays", __("Holidays"), __("Every day off. Add cuti bersama by hand; the description is shown to staff.")],
			],
		}),
		"Holiday List Assignment": form({
			fields: [
				["applicable_for", __("For"), __("A whole company or one employee.")],
				["assigned_to", __("Assigned To"), __("Which company or employee.")],
				["holiday_list", __("Holiday List"), __("The list they follow.")],
				["from_date", __("From"), __("From when. Then Submit.")],
			],
		}),
		"Leave Type": form({
			fields: [
				["leave_type_name", __("Name"), __("Shown to staff in Drea One.")],
				["is_lwp", __("Leave Without Pay"), __("Ticked: unpaid, the days lower that month's pay.")],
				["include_holiday", __("Count holidays"), __("Ticked: holidays inside the leave count as leave days.")],
				["allow_negative", __("Allow Negative Balance"), __("Ticked: may be taken before the days are given.")],
				["is_carry_forward", __("Carry Forward"), __("Unused days move to the next period, up to the maximum.")],
				["max_leaves_allowed", __("Limits"), __("On the Limits tab: the most days per period and in a row.")],
			],
		}),
		"Leave Policy": form({
			fields: [
				["title", __("Name"), __("For example \"Karyawan Tetap\".")],
				["leave_policy_details", __("Leave types"), __("Each leave type and its days per period. Submit when done.")],
			],
		}),
		"Leave Period": form({
			fields: [
				["from_date", __("Dates"), __("The leave year.")],
				["company", __("Company"), __("Whose leave year.")],
				["is_active", __("Is Active"), __("Only active periods are used.")],
			],
		}),
		"Leave Encashment": form({
			fields: [
				["employee", __("Employee"), __("Who is paid.")],
				["leave_type", __("Leave Type"), __("Must allow encashment.")],
				["encashment_days", __("Days"), __("How many unused days to pay; the amount is worked out.")],
				["encashment_date", __("Payroll"), __("Paid through the payroll of this date (as Additional Salary).")],
			],
		}),
		"Leave Block List": form({
			fields: [
				["leave_block_list_name", __("Name"), __("For example \"Year-end close\".")],
				["leave_block_list_dates", __("Blocked days"), __("Days no leave may be taken.")],
				["leave_block_list_allowed", __("Allowed"), __("People who may still take leave those days.")],
			],
		}),
		"Compensatory Leave Request": form({
			fields: [
				["employee", __("Employee"), __("Who worked on the holiday.")],
				["work_from_date", __("Days worked"), __("From and To: only days on their holiday list count.")],
				["reason", __("Reason"), __("What the work was.")],
				["approvers", __("Approvers"), __("Their supervisors decide, the way they decide on leave.")],
				["expires_on", __("Expires On"), __("The days off must be used by then (HR Settings: Cuti Pengganti expiry).")],
			],
		}),
	};

	const R = {
		"Employee Leave Balance": report(__("Leave Balance"),
			__("Per person and leave type: days given, taken, expired and left."),
			__("The period, the company, and optionally one person or department."),
			__("One row per person and leave type.")),
		"Employee Leave Balance Summary": report(__("Leave Balance Summary"),
			__("Days left per leave type for everyone, on one date."),
			__("The date and the company."),
			__("One row per person, one column per leave type.")),
		"Employees working on a holiday": report(__("Working on a holiday"),
			__("Who has attendance (present or half day) on a holiday."),
			__("The period, the company and the holiday list."),
			__("One row per person and holiday; useful to check Overtime Submissions.")),
	};

	window.hrms_tours.add({ list: L, form: F, report: R });
})();
