// HR Setup tutorials (owner, 24 Nov 2026): HR Dashboard, Employee, the masters, HR Settings.
// Engine: hr_tours.js.
(function () {
	const { step, top, card, sidebar_link, again } = window.hrms_tours.h;
	const { list, form } = window.hrms_tours.builders;

	const page = {
		"hr-dashboard": () => [
			step(null, __("HR Dashboard"),
				__("Today at a glance for HR: who is in, who is away, what is waiting for you. It opens when you sign in.")),
			step(top(".page-form"), __("Company"),
				__("Show one company, or leave it empty for all.")),
			step(top(".hrd-stats"), __("Today in numbers"),
				__("Active employees, checked in today, on leave today, and leave requests still waiting.")),
			step(card(__("Attendance today")), __("Attendance today"),
				__("Who checked in on time, late, not yet, or is away. Late = after the shift's grace period.")),
			step(card(__("Leave requests")), __("Leave requests"),
				__("Requests waiting for a decision. Open one to see it; the approver decides in Drea One or here.")),
			step(card(__("Checked in outside the office today")), __("Outside the office"),
				__("Check-ins further from the office than its radius, with the reason the person gave (Meeting di Luar / Sudah izin Supervisor).")),
			step(card(__("Documents still missing")), __("Documents still missing"),
				__("Leave that needs a supporting document (for example a doctor's note) that has not been uploaded yet.")),
			step(top(".hrd-settings"), __("Module settings"),
				__("Shortcuts to the settings of each part: leave and holidays, shifts and check-in, departments and approvers, office locations, payroll.")),
			again,
		],
		"organizational-chart": () => [
			step(null, __("Organizational Chart"),
				__("Who reports to whom, from each employee's <b>Reports to</b>. Pick a company at the top, click a person to open their team.")),
			again,
		],
	};

	const L = {
		Employee: list(__("Employees"),
			__("One record per person. Drea One, leave, attendance and payroll all start from it."), {
				rows: [__("Status"), __("<b>Active</b> people get shifts, leave and payroll; <b>Left</b> ends them (with a Relieving Date).")],
				filters: __("Filter by name, company, department or status."),
				add: [__("A new person"), __("Name, gender, date of birth, date of joining and company; then their login (User ID) so they can use Drea One.")],
			}),
		Company: list(__("Companies"),
			__("The legal entities that employ people and pay salaries. Payroll runs per company."), {
				add: [__("A new company"), __("Only for a new legal entity.")],
			}),
		Branch: list(__("Branches"), __("Office or site names. Optional: used to filter payroll, attendance and leave."), {
			add: [__("A new branch"), __("Just a name, for example Jakarta or Tangerang.")],
		}),
		Department: list(__("Departments"),
			__("Teams per company. A department decides its people's supervisors."), {
				rows: [__("Per company"), __("Each company has its own departments, named \"Team - ABBR\".")],
				add: [__("A new department"), __("Pick the company and set its leave approvers.")],
			}),
		Designation: list(__("Designations"), __("Job titles, shown on the employee and in reports."), {
			add: [__("A new job title"), __("Just the name.")],
		}),
		"Employee Group": list(__("Employee Groups"), __("Named groups of people, for example for notifications or filters."), {
			add: [__("A new group"), __("A name, then add the people.")],
		}),
		"Employee Grade": list(__("Employee Grades"),
			__("Levels with a default salary structure and base pay, used when assigning salaries to many people."), {
				add: [__("A new grade"), __("The default structure and base pay for people of this grade.")],
			}),
	};

	const F = {
		Employee: form({
			intro: [__("An employee"), __("Their details, where they work, their days and shifts, their approvers and their pay details. The tabs at the top group them.")],
			fields: [
				["first_name", __("Name"), __("First and last name; the Full Name fills in by itself.")],
				["date_of_joining", __("Date of Joining"), __("Their first day. Leave and payroll count from it.")],
				["status", __("Status"), __("Active while they work here. <b>Left</b>, with a Relieving Date, ends shifts, automatic check-in and payroll.")],
				["user_id", __("User ID"), __("Their login (their email) for Drea One. Without it they cannot sign in.")],
				["company", __("Company"), __("The legal entity that pays them.")],
				["department", __("Department"), __("Decides their supervisors (the department's leave approvers).")],
				["employment_type", __("Employment Type"), __("Types set in HR Settings as without leave allocation (for example interns) get no paid leave; their leave moves their Contract End Date.")],
				["holiday_list", __("Holiday List"), __("Their days off. Empty: the company's default.")],
				["default_shift", __("Default Shift"), __("Used on days without a Shift Assignment.")],
				["leave_approver", __("Leave Approver"), __("Who approves their leave (unless HR Settings approves by levels, then the department's approvers decide).")],
				["auto_checkin", __("Automatic Check-in"), __("Ticked: checked in at shift start and out at shift end by itself, every working day. Only HR can change it.")],
				["bank_ac_no", __("Bank account"), __("For the salary transfer to the bank.")],
				["ktp_number", __("Indonesian IDs"), __("NIK, NPWP and BPJS numbers. Personal data: only HR sees them.")],
			],
		}),
		Company: form({
			fields: [
				["company_name", __("Company"), __("The legal name.")],
				["abbr", __("Abbreviation"), __("A short code added to its accounts, departments and cost centers, for example DST.")],
				["default_holiday_list", __("Default Holiday List"), __("Everyone's days off, unless an employee has their own.")],
			],
		}),
		Branch: form({ fields: [["branch", __("Branch"), __("The office or site name.")]] }),
		Department: form({
			fields: [
				["department_name", __("Department"), __("The team's name; the company's abbreviation is added.")],
				["company", __("Company"), __("The company it belongs to.")],
				["leave_approvers", __("Leave approvers"), __("The team's supervisors: they approve leave and Overtime Submission and see outside-office check-ins. The first is the default.")],
				["shift_request_approver", __("Shift request approvers"), __("Who approves the team's shift requests.")],
			],
		}),
		Designation: form({ fields: [["designation_name", __("Designation"), __("The job title.")]] }),
		"Employee Group": form({
			fields: [
				["employee_group_name", __("Name"), __("The group's name.")],
				["employee_list", __("Employees"), __("The people in it.")],
			],
		}),
		"Employee Grade": form({
			fields: [
				["default_salary_structure", __("Default Salary Structure"), __("New salary assignments for people of this grade start with this structure.")],
				["default_base_pay", __("Default Base Pay"), __("…and this base.")],
			],
		}),
		"HR Settings": form({
			intro: [__("HR Settings"), __("Rules for the whole HR system. The tabs group them: Employee, Leaves, Attendance, Payroll.")],
			fields: [
				["leave_approval_by_levels", __("Approve leave by levels"), __("Leave goes to all of the department's approvers: approved once every Required approver and one Regular approver approve; rejected as soon as anyone rejects.")],
				["employment_types_without_leave_allocation", __("Types without leave allocation"), __("These employment types get no paid leave; each approved leave day moves their Contract End Date one working day later.")],
				["leave_types_requiring_document", __("Leave that needs a document"), __("For example sick leave: a reminder stays on the dashboards until the document is uploaded.")],
				["compensatory_leave_type", __("Cuti Pengganti"), __("Worked on a holiday? Employees send an Overtime Submission in Drea One; once approved they get the same days off of this leave type.")],
				["require_selfie_for_checkin", __("Selfie check-in"), __("Employees check in with their camera in Drea One, and can no longer edit their own check-ins.")],
				["pay_period_start_day", __("Pay period"), __("Attendance for payroll counts from this day of the month to the day before it next month (19 = 19th to 18th).")],
				["show_salary_in_employee_app", __("Salary in Drea One"), __("Everyone sees their own salary slips in Drea One.")],
			],
		}),
	};

	window.hrms_tours.add({ list: L, form: F, page });
})();
