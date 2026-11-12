// Payroll tutorial (owner, 12 Nov 2026), with driver.js (MIT, public/js/vendor):
// - the Payroll Entry list: a short tour, by itself the first time an HR person opens it;
// - a Payroll Entry form: the full tour, by itself the first time they open one, and from its
//   "Tutorial" button any time; Salary Component: a short tour from its button;
// - "Tutorial" (? icon) in the Payroll menu opens the list with #tutorial and replays the list tour.
// "First time" is remembered on the person's account (hrms.api.mark_tour_seen, a user default).
// The full written guide is the Payroll Manual Guide.
// Plain file (hooks.app_include_js), loaded after the desk bundle and driver.js.
(function () {
	const make = () => window.driver && window.driver.js && window.driver.js.driver;
	const HR_ROLES = ["HR Manager", "HR User"];
	const is_hr = () => HR_ROLES.some((r) => frappe.user.has_role(r));
	const seen = (tour) => cint(frappe.defaults.get_user_default(`hrms_tour_${tour}`));
	const mark_seen = (tour) => {
		frappe.defaults.set_user_default_local(`hrms_tour_${tour}`, "1");
		frappe.xcall("hrms.api.mark_tour_seen", { tour }).catch(() => {});
	};
	let running = false;

	const shown = (el) => (el && el.offsetParent ? el : undefined);
	// a field on the form; switches to its tab first (Frappe's scroll_to_field does that). A field
	// Frappe hides (an empty read-only one) falls back to its section, else the step shows centred.
	const field = (frm, fieldname, section) => () => {
		if (!frm.fields_dict[fieldname]) return undefined;
		frm.scroll_to_field(fieldname, false);
		const el = shown(document.querySelector(`.frappe-control[data-fieldname="${fieldname}"]`));
		if (el || !section || !frm.fields_dict[section]) return el;
		frm.scroll_to_field(section, false);
		const w = frm.fields_dict[section].wrapper;
		const node = w && (w[0] || w);
		return shown(node && node.closest ? node.closest(".form-section") || node : undefined);
	};
	// a button on the page's toolbar, by its label (a group's own button for grouped ones)
	const button = (label) => () => {
		window.scrollTo({ top: 0 });
		return [...document.querySelectorAll(".page-head .page-actions button, .page-head .inner-group-button > button")].find(
			(b) => b.offsetParent && b.innerText.trim().startsWith(label)
		);
	};
	// no element = a popover in the middle of the screen (driver.js wants the key left out, not null)
	const step = (element, title, description) =>
		element ? { element, popover: { title, description } } : { popover: { title, description } };

	function start(frm, steps) {
		const driver = make();
		if (!driver) {
			frappe.msgprint(__("The tutorial could not load. Refresh the page and try again."));
			return;
		}
		if (running) return;
		running = true;
		const tour = driver({
			showProgress: true,
			allowClose: true,
			smoothScroll: true,
			nextBtnText: __("Next"),
			prevBtnText: __("Back"),
			doneBtnText: __("Done"),
			progressText: __("{{current}} of {{total}}"),
			// a step whose element is not on screen (another state of the form) shows in the middle
			steps: steps.filter(Boolean),
			onDestroyed: () => {
				running = false;
				window.scrollTo({ top: 0 });
			},
		});
		tour.drive();
	}

	// --- the Payroll Entry list --------------------------------------------------------------
	const sidebar_link = (part) => () =>
		shown([...document.querySelectorAll(".body-sidebar a, .layout-side-section a, .sidebar-item-container a")].find(
			(a) => (a.getAttribute("href") || "").includes(part)
		));

	function payroll_list_steps() {
		return [
			step(null, __("Welcome to Payroll"),
				__("Each month HR runs one Payroll Entry per company. It makes everyone's salary slip and sends Drea Finance only the totals. This short tour shows where things are.")),
			step(() => shown(document.querySelector(".frappe-list .result, .frappe-list")), __("Payroll Entries"),
				__("Every month's run is listed here with its status. Open one to see its slips and Drea Finance's answer.")),
			step(button(__("Add Payroll Entry")), __("Start a month"),
				__("Press this to start a month's payroll. Its own tutorial starts the first time you open one.")),
			step(sidebar_link("salary-structure-assignment"), __("Before the first month"),
				__("Each person needs a <b>Salary Structure Assignment</b> (their structure and base salary), or they are left out.")),
			step(sidebar_link("additional-salary"), __("Penalties and one-offs"),
				__("Late penalties, bonuses and other one-month amounts go in as <b>Additional Salary</b> before the Payroll Entry.")),
			step(sidebar_link("#tutorial"), __("Need this again?"),
				__("<b>Tutorial</b> in this menu replays this tour any time. On a Payroll Entry, the <b>Tutorial</b> button explains that screen.")),
		];
	}

	function maybe_list_tour(force) {
		const route = frappe.get_route();
		if (route[0] !== "List" || route[1] !== "Payroll Entry") return;
		const asked = force === true || window.location.hash === "#tutorial";
		if (!asked && (!is_hr() || seen("payroll_list"))) return;
		if (window.location.hash === "#tutorial") history.replaceState(null, "", window.location.pathname + window.location.search);
		// wait for the list and its toolbar to be drawn
		let tries = 0;
		const wait = setInterval(() => {
			tries += 1;
			const ready = document.querySelector(".frappe-list") && button(__("Add Payroll Entry"))();
			if (ready || tries > 40) {
				clearInterval(wait);
				if (!asked) mark_seen("payroll_list");
				start(null, payroll_list_steps());
			}
		}, 250);
	}
	frappe.router.on("change", () => setTimeout(maybe_list_tour, 300));
	$(document).on("app_ready", () => setTimeout(maybe_list_tour, 600));
	// "Tutorial" in the Payroll menu: the desk opens every web-address item in a new tab, so the
	// click is taken here and the tour plays in this tab
	$(document).on("click", 'a[href$="#tutorial"]', (e) => {
		if (!/payroll-entry#tutorial$/.test(e.currentTarget.getAttribute("href") || "")) return;
		e.preventDefault();
		e.stopImmediatePropagation();
		const route = frappe.get_route();
		if (route[0] === "List" && route[1] === "Payroll Entry") {
			maybe_list_tour(true);
		} else {
			frappe.set_route("List", "Payroll Entry").then(() => setTimeout(() => maybe_list_tour(true), 300));
		}
	});

	function payroll_entry_steps(frm) {
		const draft = frm.doc.docstatus === 0;
		const submitted = frm.doc.docstatus === 1;
		const sent = submitted && frm.doc.salary_slips_submitted;
		return [
			step(null, __("Payroll, one month at a time"),
				__("One Payroll Entry pays one company for one month. It makes a salary slip for each person; submitting the slips sends Drea Finance the totals per company and division, never a person's pay.")),
			step(field(frm, "posting_date"), __("Posting Date = pay date"),
				__("The day salaries are paid. Drea Finance books the month's journal on this date.")),
			step(field(frm, "company"), __("Company"),
				__("The legal entity paying. It needs its Drea Finance code (LE-…) in the Company form, or the send is stopped.")),
			step(field(frm, "start_date"), __("The month"),
				__("Payroll Frequency Monthly, Start Date and End Date = the month being paid (for example 1 to 30 November).")),
			step(field(frm, "drea_finance_kind"), __("Kind for Drea Finance"),
				__("Salary for the monthly pay; THR or Bonus for those runs. Finance keeps them apart.")),
			step(field(frm, "department"), __("Department (optional)"),
				__("Empty pays the whole company. Every department paid must have a Drea Finance division (DV-…).")),
			step(field(frm, "employees"), __("Employees"),
				__("<b>Get Employees</b> fills this list: everyone with a salary structure assignment for the month who has no slip yet. Check it before going on.")),
			step(field(frm, "cost_center"), __("Accounting"),
				__("Cost Center and Payment Account: the bank account salaries are paid from.")),
			draft && step(button(__("Get Employees")), __("Get Employees"),
				__("Save first, then press it. Penalties and one-off amounts must already be in as <b>Additional Salary</b> for the month.")),
			draft && step(button(__("Create Salary Slips")), __("Create Salary Slips"),
				__("Submits this entry and makes one <b>draft</b> salary slip per person. Nothing goes to Finance yet.")),
			submitted && step(null, __("Check the slips"),
				__("Open the Connections tab, Salary Slip: check gross, deductions and take-home for each person. Fix a wrong one at its source (assignment, Additional Salary) before going on.")),
			submitted && !sent && step(button(__("Submit Salary Slip")), __("Submit Salary Slip"),
				__("Submits every slip and makes the accrual journal here. With <b>Send Payroll</b> on in HR Settings, the totals go to Drea Finance within a minute.")),
			submitted && step(field(frm, "drea_finance_status", "drea_finance_section"), __("Drea Finance's Answer"),
				__("Finance's reply lands here: \"received\" (draft journal made), \"unchanged\" (already had these figures) or the list of problems to fix.")),
			sent && step(button(__("Drea Finance")), __("Drea Finance buttons"),
				__("<b>Test (nothing saved)</b> checks the totals without saving. <b>Send Totals</b> sends them, as a new version after a correction.")),
			sent && step(button(__("Make Bank Entry")), __("Pay"),
				__("Records the payment from the bank account once salaries are transferred.")),
			step(null, __("Done"),
				__("Finance checks the draft journal in Drea Finance, Salary, and posts it. The Payroll Manual Guide has the setup, the edge cases and the error messages.")),
		];
	}

	function salary_component_steps(frm) {
		return [
			step(field(frm, "type"), __("Type"),
				__("Earning, Deduction (taken from pay, or a cut such as a late penalty) or Employer Contribution (the company's BPJS share).")),
			step(field(frm, "drea_finance_component"), __("Drea Finance code"),
				__("Which line this is in Finance: SALARY, INCENTIVE, PPH21_WITHHELD, BPJS_… A late penalty is a Deduction with code <b>SALARY</b>: Finance sees lower salary. A component without a code stops the send.")),
			step(field(frm, "round_to_the_nearest_integer"), __("Round to the Nearest Integer"),
				__("Tick it: Finance takes whole rupiah only. 1% of 6,333,333 becomes 63,333.")),
			step(field(frm, "remove_if_zero_valued"), __("Remove if Zero Valued"),
				__("Untick it to keep a 0 line on the slip (for example BPJS TK 0). A 0 line is never sent to Finance either way.")),
			step(field(frm, "accounts"), __("Accounts"),
				__("One row per company. An Employer Contribution needs both the expense account and the liability account.")),
		];
	}

	// Payroll Entry's own refresh clears every custom button on a submitted entry and adds its own,
	// so it calls add_button itself, last (payroll_entry.js); Salary Component clears nothing
	window.hrms_payroll_tour = {
		add_button(frm) {
			frm.add_custom_button(__("Tutorial"), () => start(frm, payroll_entry_steps(frm)));
			// the first Payroll Entry an HR person opens: the tour starts by itself, once
			if (is_hr() && !seen("payroll_form") && !running) {
				mark_seen("payroll_form");
				setTimeout(() => start(frm, payroll_entry_steps(frm)), 800);
			}
		},
	};
	frappe.ui.form.on("Salary Component", {
		refresh(frm) {
			frm.add_custom_button(__("Tutorial"), () => start(frm, salary_component_steps(frm)));
		},
	});
})();
