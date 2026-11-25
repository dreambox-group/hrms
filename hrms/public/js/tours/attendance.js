// Shift & Attendance tutorials (owner, 24 Nov 2026): check-ins, attendance, shifts, office
// locations, overtime, reports. Engine: hr_tours.js.
(function () {
	const { step } = window.hrms_tours.h;
	const { list, form, report } = window.hrms_tours.builders;

	const L = {
		"Employee Checkin": list(__("Employee Checkins"),
			__("Every check-in and check-out: from Drea One (selfie and location), from Automatic Check-in, or entered by HR."), {
				rows: [__("The log"), __("Time, IN or OUT, and the device: \"Auto check-in\" marks the automatic ones.")],
				filters: __("Filter by employee or time."),
				add: [__("Enter one by hand"), __("For example when someone's phone failed. Staff with selfie check-in cannot add or edit their own.")],
			}),
		Attendance: list(__("Attendance"),
			__("One record per person per day: Present, Absent, On Leave, Half Day or Work From Home. Payroll and Drea One's \"this pay period\" read it."), {
				rows: [__("Where it comes from"), __("Made by itself from check-ins (the shift's auto attendance) and from approved leave. HR can mark days with the Employee Attendance Tool.")],
				filters: __("Filter by employee, date or status."),
				add: [__("Mark one day"), __("One person, one day. For many people use <b>Employee Attendance Tool</b>.")],
			}),
		"Attendance Request": list(__("Attendance Requests"),
			__("Someone asks to count days as Work From Home or On Duty (working elsewhere) without checking in."), {
				add: [__("A new request"), __("The person, the dates and the reason; approved requests mark attendance.")],
			}),
		"Shift Assignment": list(__("Shift Assignments"),
			__("Who works which shift, from when, and at which office. Check-in, lateness and automatic check-in use it."), {
				rows: [__("Active"), __("Only <b>Active</b>, submitted assignments count. No end date = ongoing.")],
				filters: __("Filter by employee, shift or date."),
				add: [__("Assign a shift"), __("One person. For many people use <b>Shift Assignment Tool</b>.")],
			}),
		"Shift Schedule Assignment": list(__("Shift Schedule Assignments"),
			__("A repeating pattern for a person (for example Mon–Fri office); Shift Assignments are made from it by themselves."), {
				add: [__("Give a pattern"), __("The person, the Shift Schedule and the office.")],
			}),
		"Shift Request": list(__("Shift Requests"), __("Someone asks to work another shift for some days; the approver decides."), {
			add: [__("A new request"), __("The person, the shift, the dates and the approver.")],
		}),
		"Shift Location": list(__("Shift Locations"),
			__("Offices with their position and check-in radius. Check-ins further away need a reason."), {
				add: [__("A new office"), __("The name, the position (Fetch Geolocation on site) and the radius in metres.")],
			}),
		"Shift Type": list(__("Shift Types"), __("Working hours: start, end, when someone is late, how attendance is marked."), {
			add: [__("A new shift"), __("Start and end time, the late grace period and auto attendance.")],
		}),
		"Shift Schedule": list(__("Shift Schedules"), __("A shift on certain weekdays, for Shift Schedule Assignments."), {
			add: [__("A new schedule"), __("The shift, every week or every two, and the days.")],
		}),
		"Overtime Type": list(__("Overtime Types"), __("How overtime is paid: the pay component and the rate."), {
			add: [__("A new type"), __("The salary component, how the amount is worked out and the multipliers.")],
		}),
		"Overtime Slip": list(__("Overtime Slips"), __("Overtime worked in a period, per person; paid through payroll."), {
			add: [__("A new slip"), __("The person and the period; the overtime is filled from attendance.")],
		}),
	};

	const F = {
		"Employee Checkin": form({
			fields: [
				["employee", __("Employee"), __("Whose check-in.")],
				["log_type", __("Log Type"), __("IN or OUT.")],
				["time", __("Time"), __("When. Before the shift's start plus its grace period = on time.")],
				["device_id", __("Device"), __("\"Auto check-in\" for Automatic Check-in.")],
				["office_distance", __("Office range"), __("How far from the office; further than its radius needs a reason.")],
				["outside_office_reason", __("Reason"), __("Meeting di Luar or Sudah izin Supervisor; supervisors and HR see it the same day.")],
				["selfie", __("Selfie"), __("The photo taken at check-in in Drea One. Deleted after the days set in HR Settings.")],
			],
		}),
		Attendance: form({
			fields: [
				["employee", __("Employee"), __("Whose day.")],
				["attendance_date", __("Date"), __("The day.")],
				["status", __("Status"), __("Present, Absent, On Leave, Half Day or Work From Home. Absent and unpaid leave lower the month's pay.")],
				["late_entry", __("Late Entry"), __("Checked in after the shift's grace period.")],
				["in_time", __("In and out"), __("The first check-in and last check-out of the day.")],
			],
			end: [__("Submit"), __("Submitted attendance counts for payroll. To change it, Cancel and Amend.")],
		}),
		"Employee Attendance Tool": form({
			intro: [__("Employee Attendance Tool"), __("Marks one day for many people at once.")],
			fields: [
				["date", __("Date"), __("The day to mark.")],
				["company", __("Who"), __("Narrow by company, department, branch or shift.")],
				["status", __("Status"), __("Present, Absent, Half Day or Work From Home for the people you tick.")],
				["unmarked_employees_html", __("Pick people"), __("Tick the people not yet marked, then <b>Mark Attendance</b>.")],
			],
		}),
		"Attendance Request": form({
			fields: [
				["employee", __("Employee"), __("Who.")],
				["from_date", __("Dates"), __("From and To.")],
				["reason", __("Reason"), __("Work From Home or On Duty.")],
				["explanation", __("Explanation"), __("Details for the approver. Submit after approval to mark the days.")],
			],
		}),
		"Shift Assignment": form({
			fields: [
				["employee", __("Employee"), __("Who.")],
				["shift_type", __("Shift"), __("Their working hours.")],
				["shift_location", __("Office"), __("The office for check-in. Empty, or an office with radius 0 = no location check (working from home).")],
				["start_date", __("Dates"), __("Start, and End if it stops (empty = ongoing). Then Submit.")],
				["status", __("Status"), __("Set Inactive to stop it early.")],
			],
		}),
		"Shift Schedule Assignment": form({
			fields: [
				["employee", __("Employee"), __("Who.")],
				["shift_schedule", __("Shift Schedule"), __("The weekly pattern.")],
				["shift_location", __("Office"), __("The office for check-in.")],
				["enabled", __("Enabled"), __("While on, Shift Assignments are made from it by themselves.")],
			],
		}),
		"Shift Assignment Tool": form({
			intro: [__("Shift Assignment Tool"), __("Gives a shift to many people at once, or answers many shift requests.")],
			fields: [
				["action", __("Action"), __("Assign a shift, assign a schedule, or process shift requests.")],
				["shift_type", __("Shift"), __("Which shift.")],
				["shift_location", __("Office"), __("Their office for check-in.")],
				["start_date", __("Dates"), __("From (and To).")],
				["employees_html", __("Pick people"), __("Narrow with the filters, tick the people, then <b>Assign Shift</b>.")],
			],
		}),
		"Shift Request": form({
			fields: [
				["employee", __("Employee"), __("Who asks.")],
				["shift_type", __("Shift"), __("The shift they want.")],
				["from_date", __("Dates"), __("From and To.")],
				["approver", __("Approver"), __("Decides: Approved makes a Shift Assignment.")],
			],
		}),
		"Shift Location": form({
			fields: [
				["location_name", __("Name"), __("The office's name.")],
				["checkin_radius", __("Check-in radius"), __("Metres (at most 500). Further away the person must give a reason. 0 = no check, for working from home.")],
				["fetch_geolocation", __("Position"), __("Press it while at the office, or type the latitude and longitude.")],
			],
		}),
		"Shift Type": form({
			fields: [
				["start_time", __("Hours"), __("Start and end time.")],
				["holiday_list", __("Holiday List"), __("Days off for this shift; empty = each person's own.")],
				["enable_auto_attendance", __("Auto attendance"), __("Marks attendance from check-ins after the shift.")],
				["working_hours_threshold_for_absent", __("Thresholds"), __("Fewer hours than this = Absent (or Half Day for the half-day threshold).")],
				["enable_late_entry_marking", __("Late"), __("Marks late entries.")],
				["late_entry_grace_period", __("Grace period"), __("Minutes after the start still on time: 60 after 08:30 = late after 09:30.")],
			],
		}),
		"Shift Schedule": form({
			fields: [
				["shift_type", __("Shift"), __("Which shift.")],
				["frequency", __("Frequency"), __("Every week or every two weeks.")],
				["repeat_on_days", __("Days"), __("The weekdays it repeats on. Submit when done.")],
			],
		}),
		"Overtime Type": form({
			fields: [
				["overtime_salary_component", __("Salary Component"), __("The pay item overtime is paid as.")],
				["overtime_calculation_method", __("Amount"), __("From the salary components, or a fixed hourly rate.")],
				["standard_multiplier", __("Multipliers"), __("× the hourly rate; higher on weekends and public holidays if set.")],
			],
		}),
		"Overtime Slip": form({
			fields: [
				["employee", __("Employee"), __("Who.")],
				["start_date", __("Period"), __("From and To.")],
				["overtime_details", __("Overtime"), __("The days and hours. Submit: paid in that period's payroll.")],
			],
		}),
	};

	const R = {
		"Monthly Attendance Sheet": report(__("Monthly Attendance Sheet"),
			__("A month at a glance: one row per person, one column per day."),
			__("The month and year (or a date range), the company, optionally a department or person."),
			__("P present, A absent, L on leave, HD/P or HD/A half day, WFH work from home, H holiday, WO weekly off.")),
		"Shift Attendance": report(__("Shift Attendance"),
			__("Per day and person: shift, check-in and check-out times, late and early."),
			__("The dates, the company, optionally a shift, department or person; tick Late Entry to see only late days."),
			__("One row per person per day.")),
	};

	window.hrms_tours.add({ list: L, form: F, report: R });
})();
