// Copyright (c) 2026, Dreambox and contributors
// For license information, please see license.txt

frappe.pages["hr-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("HR Dashboard"),
		single_column: true,
	});
	wrapper.hr_dashboard = new HRDashboard(page, wrapper);
};

frappe.pages["hr-dashboard"].on_page_show = function (wrapper) {
	wrapper.hr_dashboard?.refresh();
};

const STATUS_STYLES = {
	"Checked in": "green",
	Late: "orange",
	"Not yet in": "gray",
	"On leave": "blue",
};

const MODULE_SETTINGS = [
	{
		title: __("HR Settings"),
		text: __("Leave by levels, selfie check-in, leave calendar, notifications"),
		route: ["Form", "HR Settings"],
	},
	{
		title: __("Leave & holidays"),
		text: __("Leave types and calendar labels, holiday lists, leave policies"),
		route: ["List", "Leave Type"],
	},
	{
		title: __("Shifts & check-in"),
		text: __("Shift types, office locations and radius, auto attendance"),
		route: ["List", "Shift Type"],
	},
	{
		title: __("Departments & approvers"),
		text: __("Required and Regular leave approvers per department"),
		route: ["List", "Department"],
	},
	{
		title: __("Payroll settings"),
		text: __("Payroll periods, salary components and structures"),
		route: ["Form", "Payroll Settings"],
	},
];

class HRDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.state = { leaveTab: "waiting", awayTab: "today" };
		this.$body = $(`<div class="hr-dashboard"></div>`).appendTo(page.main);

		this.company = page.add_field({
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			label: __("Company"),
			placeholder: __("All companies"),
			change: () => this.refresh(),
		});
		page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");

		this.$body.on("click", "[data-route]", (e) => {
			e.preventDefault();
			frappe.set_route(...JSON.parse(e.currentTarget.dataset.route));
		});
		this.$body.on("click", "[data-tab]", (e) => {
			const { tab, group } = e.currentTarget.dataset;
			this.state[group] = tab;
			this.render();
		});
	}

	refresh() {
		frappe.call({
			method: "hrms.api.hr_dashboard.get_dashboard_data",
			args: { company: this.company.get_value() || null },
			callback: (r) => {
				this.data = r.message;
				this.render();
			},
		});
	}

	render() {
		const d = this.data;
		if (!d) return;
		this.$body.html(`
			<div class="hrd-head">
				<div class="hrd-date">${moment(d.date).format("dddd, D MMMM YYYY")}</div>
				<h1 class="hrd-greeting">${this.greeting()}</h1>
			</div>
			<div class="hrd-stats">${this.stats(d.stats)}</div>
			<div class="hrd-grid">
				${this.attendance(d.attendance)}
				${this.leave(d.leave)}
				${this.away(d.away)}
				${this.celebrations(d.celebrations)}
				${this.shifts(d.shifts)}
				${this.headcount(d.headcount)}
				${this.changes(d.changes)}
				${this.requests(d.requests)}
				${this.missingDocuments(d.missing_documents || [])}
			</div>
			<h2 class="hrd-section-title">${__("Module settings")}</h2>
			<div class="hrd-settings">
				${MODULE_SETTINGS.map(
					(m) => `
					<a class="hrd-setting" href="#" data-route='${route(m.route)}'>
						<div class="hrd-setting-title">${m.title}</div>
						<div class="hrd-muted">${m.text}</div>
					</a>`
				).join("")}
			</div>
		`);
	}

	greeting() {
		const hour = new Date().getHours();
		const hello = hour < 12 ? __("Good morning") : hour < 17 ? __("Good afternoon") : __("Good evening");
		const name = frappe.boot.user.first_name || frappe.session.user_fullname || "";
		return `${hello}, ${esc(name)}`;
	}

	stats(s) {
		return [
			[__("Active employees"), s.active_employees, ""],
			[__("Checked in today"), s.checked_in, "green"],
			[__("On leave today"), s.on_leave, "blue"],
			[__("Leave waiting"), s.leave_waiting, s.leave_waiting ? "red" : ""],
			[__("Birthdays & anniversaries this week"), s.celebrations_this_week, ""],
		]
			.map(
				([label, value, color]) => `
				<div class="hrd-stat">
					<div class="hrd-muted">${label}</div>
					<div class="hrd-stat-value ${color ? "hrd-text-" + color : ""}">${value}</div>
				</div>`
			)
			.join("");
	}

	attendance(a) {
		const chips = Object.entries(a.counts)
			.map(
				([status, n]) => `
				<div class="hrd-chip hrd-bg-${STATUS_STYLES[status]}">
					<div class="hrd-chip-value">${n}</div>
					<div>${__(status)}</div>
				</div>`
			)
			.join("");
		const notIn = a.not_in.length
			? a.not_in
					.map(
						(row) => `
						<a class="hrd-row" href="#" data-route='${route(["Form", "Employee", row.employee])}'>
							<span>${esc(row.employee_name)} <span class="hrd-muted">· ${esc(row.department || "")}</span></span>
							<span class="hrd-muted">${time(row.shift_start) ? __("from {0}", [time(row.shift_start)]) : ""}</span>
						</a>`
					)
					.join("")
			: `<div class="hrd-empty">${__("Everyone with a shift today has checked in.")}</div>`;
		return card(
			__("Attendance today"),
			[__("Open check-ins"), ["List", "Employee Checkin"]],
			`<div class="hrd-chips">${chips}</div>
			<div class="hrd-subtitle">${__("Not checked in yet")}</div>
			${notIn}`
		);
	}

	leave(leave) {
		const tabs = [
			["waiting", __("Waiting ({0})", [leave.waiting.length])],
			["approved", __("Approved")],
			["rejected", __("Rejected")],
		];
		const rows = leave[this.state.leaveTab];
		const body = rows.length
			? rows
					.map(
						(row) => `
						<a class="hrd-row" href="#" data-route='${route(["Form", "Leave Application", row.name])}'>
							<span>
								<div class="hrd-strong">${esc(row.employee_name)}</div>
								<div class="hrd-muted">${esc(row.label)} · ${dates(row.from_date, row.to_date)} · ${__("{0} days", [row.total_leave_days])}</div>
							</span>
							<span class="hrd-muted hrd-right">${row.progress.map(esc).join("<br>")}</span>
						</a>`
					)
					.join("")
			: `<div class="hrd-empty">${__("Nothing here.")}</div>`;
		return card(
			__("Leave requests"),
			[__("All leave"), ["List", "Leave Application"]],
			tabsHtml("leaveTab", tabs, this.state.leaveTab) + body
		);
	}

	away(away) {
		const tabs = [
			["today", __("Today")],
			["week", __("This week")],
		];
		const rows = away[this.state.awayTab];
		const body = rows.length
			? rows
					.map(
						(row) => `
						<div class="hrd-row">
							<span>
								<div class="hrd-strong">${esc(row.label)} - ${esc(row.employee_name)}</div>
								<div class="hrd-muted">${esc(row.department || "")}</div>
							</span>
							<span class="hrd-muted">${dates(row.from_date, row.to_date)}</span>
						</div>`
					)
					.join("")
			: `<div class="hrd-empty">${__("Nobody is away.")}</div>`;
		return card(
			__("Who's away"),
			[__("Leave calendar"), ["List", "Leave Application", "Calendar"]],
			tabsHtml("awayTab", tabs, this.state.awayTab) + body
		);
	}

	celebrations(rows) {
		const body = rows.length
			? rows
					.map(
						(c) => `
						<div class="hrd-row">
							<span><span class="hrd-strong">${esc(c.employee_name)}</span>
								<span class="hrd-muted">· ${
									c.kind === "Birthday" ? __("Birthday") : __("{0} years with us", [c.years])
								}</span></span>
							<span class="${c.date === this.data.date ? "hrd-text-red hrd-strong" : "hrd-muted"}">${day(c.date, this.data.date)}</span>
						</div>`
					)
					.join("")
			: `<div class="hrd-empty">${__("No birthdays or anniversaries this week.")}</div>`;
		return card(__("Birthdays & work anniversaries"), null, body);
	}

	shifts(rows) {
		const body = rows.length
			? rows
					.map(
						(s) => `
						<div class="hrd-row">
							<span>
								<div class="hrd-strong">${esc(s.name)}</div>
								<div class="hrd-muted">${esc(s.locations.join(", ") || __("No office location set"))}</div>
							</span>
							<span class="hrd-right">${time(s.start)}–${time(s.end)}<br><span class="hrd-muted">${__("{0} people", [s.people])}</span></span>
						</div>`
					)
					.join("")
			: `<div class="hrd-empty">${__("No shifts today.")}</div>`;
		return card(__("Shifts today"), [__("Shift assignments"), ["List", "Shift Assignment"]], body);
	}

	headcount(rows) {
		const max = Math.max(1, ...rows.map((r) => r.count));
		const body = rows
			.map(
				(r) => `
				<div class="hrd-bar-row">
					<span class="hrd-ellipsis">${esc(r.department)}</span>
					<span class="hrd-bar"><span style="width: ${(100 * r.count) / max}%"></span></span>
					<span class="hrd-strong hrd-right">${r.count}</span>
				</div>`
			)
			.join("");
		return card(__("Headcount by department"), [__("Employees"), ["List", "Employee"]], body);
	}

	changes(rows) {
		const kinds = {
			Joins: ["green", __("Joins")],
			Leaves: ["gray", __("Leaves")],
			"Contract ends": ["orange", __("Contract ends")],
			"Internship ends": ["orange", __("Internship ends")],
			"Probation ends": ["orange", __("Probation ends")],
		};
		const body = rows.length
			? rows
					.map((c) => {
						const [color, label] = kinds[c.kind];
						return `
						<a class="hrd-row" href="#" data-route='${route(["Form", "Employee", c.name])}'>
							<span><span class="hrd-strong">${esc(c.employee_name)}</span> <span class="hrd-muted">· ${esc(c.department || "")}</span></span>
							<span><span class="hrd-pill hrd-bg-${color}">${label}</span> <span class="hrd-muted">${frappe.datetime.str_to_user(c.date)}</span></span>
						</a>`;
					})
					.join("")
			: `<div class="hrd-empty">${__("Nothing in the next 30 days.")}</div>`;
		return card(__("Joining, leaving & contracts ending"), null, body);
	}

	missingDocuments(rows) {
		const body = rows.length
			? rows
					.map(
						(row) => `
						<a class="hrd-row" href="#" data-route='${route(["Form", "Leave Application", row.name])}'>
							<span>
								<div class="hrd-strong">${esc(row.label)} - ${esc(row.employee_name)}</div>
								<div class="hrd-muted">${dates(row.from_date, row.to_date)}</div>
							</span>
							<span class="hrd-pill ${row.overdue ? "hrd-badge" : "hrd-bg-orange"}">
								${row.overdue ? __("Overdue") : __("Due {0}", [frappe.datetime.str_to_user(row.document_due_date)])}
							</span>
						</a>`
					)
					.join("")
			: `<div class="hrd-empty">${__("No supporting documents are missing.")}</div>`;
		return card(__("Documents still missing"), null, body);
	}

	requests(rows) {
		const body = rows
			.map(
				(r) => `
				<a class="hrd-row" href="#" data-route='${route(["List", r.doctype, { docstatus: 0 }])}'>
					<span>${esc(r.label)}</span>
					<span class="hrd-pill ${r.count ? "hrd-badge" : "hrd-bg-gray"}">${r.count}</span>
				</a>`
			)
			.join("");
		return card(__("Other requests waiting"), null, body);
	}
}

function card(title, link, body) {
	const linkHtml = link ? `<a href="#" class="hrd-link" data-route='${route(link[1])}'>${link[0]}</a>` : "";
	return `
		<section class="hrd-card">
			<div class="hrd-card-head"><h2>${title}</h2>${linkHtml}</div>
			${body}
		</section>`;
}

function tabsHtml(group, tabs, current) {
	return `<div class="hrd-tabs" role="tablist">${tabs
		.map(
			([id, label]) => `
			<button type="button" role="tab" class="hrd-tab ${id === current ? "active" : ""}"
				aria-selected="${id === current}" data-group="${group}" data-tab="${id}">${label}</button>`
		)
		.join("")}</div>`;
}

function route(parts) {
	return frappe.utils.escape_html(JSON.stringify(parts));
}

function esc(text) {
	return frappe.utils.escape_html(text == null ? "" : String(text));
}

function dates(from, to) {
	const start = frappe.datetime.str_to_user(from);
	return from === to ? start : `${start} – ${frappe.datetime.str_to_user(to)}`;
}

function time(datetime) {
	return datetime ? moment(datetime).format("HH:mm") : "";
}

function day(date, today) {
	const diff = moment(date).diff(moment(today), "days");
	if (diff === 0) return __("Today");
	if (diff === 1) return __("Tomorrow");
	return moment(date).format("ddd D MMM");
}
