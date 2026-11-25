// HR desk tutorials, with driver.js (MIT, public/js/vendor). The engine; what each page says is in
// public/js/tours/*.js (payroll, hr_setup, leaves, attendance), which register with
// window.hrms_tours.add({ list, form, report, page }).
// - Payroll (12 Nov 2026), every Payroll page (24 Nov 2026), HR Setup, Leaves, Shift & Attendance
//   (24 Nov 2026).
// - Every list, report and page with a tutorial gets a "Tutorial" button at the top; every form
//   with one gets a "Tutorial" button too.
// - "Tutorial" (? icon) in a module's sidebar plays the tutorial of the page you are on, else that
//   module's main list's.
// - Only the Payroll Entry list and form start by themselves, the first time an HR person opens
//   them ("first time" is a user default, hrms.api.mark_tour_seen); the others from their button.
// Plain files (hooks.app_include_js), loaded after the desk bundle and driver.js. Raise the ?v= in
// hooks.py when they change: the browser keeps /assets files 12 hours.
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
	const TOURS = { list: {}, form: {}, report: {}, page: {} };

	// --- finding things on the page ------------------------------------------------------------
	const shown = (el) => (el && el.offsetParent ? el : undefined);
	// the desk keeps earlier pages in the document, hidden: take the first one on screen
	const vis = (selector) => [...document.querySelectorAll(selector)].find((el) => el.offsetParent);
	// A field on THIS form (earlier forms stay in the page, hidden); switches to its tab first. A
	// field Frappe hides (an empty read-only one) falls back to its section, else the step shows
	// centred.
	const node_of = (control) => {
		const w = control && (control.$wrapper || control.wrapper);
		return w && (w[0] || w);
	};
	const field = (frm, fieldname, section) => () => {
		const control = frm.fields_dict[fieldname];
		if (!control) return undefined;
		frm.scroll_to_field(fieldname, false);
		const node = node_of(control);
		const el = shown(node && node.closest ? node.closest(".frappe-control") || node : undefined);
		if (el || !section || !frm.fields_dict[section]) return el;
		frm.scroll_to_field(section, false);
		const s = node_of(frm.fields_dict[section]);
		return shown(s && s.closest ? s.closest(".form-section") || s : undefined);
	};
	// a button on the page's toolbar, by its label (a group's own button for grouped ones)
	const button = (label) => () => {
		window.scrollTo({ top: 0 });
		return [...document.querySelectorAll(".page-head .page-actions button, .page-head .inner-group-button > button")].find(
			(b) => b.offsetParent && b.innerText.trim().startsWith(label)
		);
	};
	const top = (selector) => () => {
		window.scrollTo({ top: 0 });
		return vis(selector);
	};
	const sidebar_link = (part) => () =>
		shown([...document.querySelectorAll(".body-sidebar a, .layout-side-section a, .sidebar-item-container a")].find(
			(a) => (a.getAttribute("href") || "").includes(part)
		));
	// a card on a custom page (HR Dashboard), by its heading
	const card = (title) => () =>
		[...document.querySelectorAll(".hrd-card")].find(
			(c) => c.offsetParent && (c.querySelector("h2")?.innerText || "").trim().startsWith(title)
		);
	// no element = a popover in the middle of the screen (driver.js wants the key left out, not null)
	const step = (element, title, description) =>
		element ? { element, popover: { title, description } } : { popover: { title, description } };

	const list_rows = top(".frappe-list .result, .frappe-list");
	const list_filters = top(".page-form");
	const add_button = button(__("Add"));
	const report_table = top(".report-wrapper .dt-scrollable, .report-wrapper, .page-body .layout-main-section");
	const report_menu = top(".page-head .menu-btn-group > button, .page-head .menu-btn-group");
	const again = step(sidebar_link("#tutorial"), __("Need this again?"),
		__("<b>Tutorial</b> at the top of the page, or in this menu, replays the tour of the page you are on."));

	// --- builders for the usual shapes ---------------------------------------------------------
	// a list: what it is, the rows, the filters, the Add button, then "Need this again?"
	function list(title, intro, opts = {}) {
		return () => [
			step(null, title, intro),
			opts.rows && step(list_rows, opts.rows[0], opts.rows[1]),
			opts.filters !== false && step(list_filters, __("Find what you need"), opts.filters || __("Type in the boxes above the list to filter it, for example by employee or status.")),
			...(opts.extra || []).map((s) => step(s[0], s[1], s[2])),
			opts.add && step(add_button, opts.add[0], opts.add[1]),
			again,
		];
	}
	// a form: an optional intro, one step per [fieldname, title, text, section?], an optional end
	function form(opts) {
		return (frm) => [
			opts.intro && step(null, opts.intro[0], opts.intro[1]),
			...opts.fields.map((f) => (typeof f[0] === "function" ? step(f[0], f[1], f[2]) : step(field(frm, f[0], f[3]), f[1], f[2]))),
			opts.end && step(null, opts.end[0], opts.end[1]),
		];
	}
	// a report: what it shows, its filters, the table, the menu
	function report(title, intro, filters_text, table_text) {
		return () => [
			step(null, title, intro),
			step(list_filters, __("Filters"), filters_text),
			step(report_table, __("The report"), table_text),
			step(report_menu, __("Export or print"), __("This menu has <b>Export</b> (Excel or CSV) and <b>Print</b>.")),
			again,
		];
	}

	// --- running a tour ------------------------------------------------------------------------
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

	// the tour of the page now open, or null
	function current_tour() {
		const route = frappe.get_route();
		if (route[0] === "Form" && TOURS.form[route[1]] && window.cur_frm && cur_frm.doctype === route[1]) {
			return () => start(cur_frm, TOURS.form[route[1]](cur_frm));
		}
		if (route[0] === "List" && TOURS.list[route[1]]) return () => start(null, TOURS.list[route[1]]());
		if (route[0] === "query-report" && TOURS.report[route[1]]) return () => start(null, TOURS.report[route[1]]());
		if (TOURS.page[route[0]] && route.length === 1) return () => start(null, TOURS.page[route[0]]());
		return null;
	}

	// --- buttons -------------------------------------------------------------------------------
	const has_tutorial_button = () =>
		[...document.querySelectorAll(".page-head .page-actions button")].some(
			(b) => b.offsetParent && b.innerText.trim() === __("Tutorial")
		);
	// added again on every visit, with the tour of the page now open: every report shares one page,
	// and a report clears its toolbar when it loads
	function add_page_button(page, run) {
		if (!page) return;
		page.remove_inner_button && page.remove_inner_button(__("Tutorial"));
		page.add_inner_button(__("Tutorial"), run);
	}
	// A Tutorial button on lists, reports and pages, once drawn. Checked for 10 seconds and put back
	// if the page clears its toolbar while loading (reports do). Also plays a tour asked for from
	// the sidebar on another page (pending).
	let pending = window.location.hash === "#tutorial";
	function on_route() {
		const route = frappe.get_route();
		let tries = 0;
		const wait = setInterval(() => {
			tries += 1;
			const now = frappe.get_route();
			if (now[0] !== route[0] || now[1] !== route[1] || tries > 40) return clearInterval(wait);
			let page = null;
			if (route[0] === "List" && TOURS.list[route[1]] && window.cur_list && cur_list.doctype === route[1]) {
				page = cur_list.page;
			} else if (route[0] === "query-report" && TOURS.report[route[1]] && frappe.query_report?.report_name === route[1]) {
				page = frappe.query_report.page;
			} else if (TOURS.page[route[0]] && route.length === 1) {
				page = frappe.container?.page?.page;
			}
			if (!page) return;
			if (!has_tutorial_button()) add_page_button(page, () => current_tour()?.());
			if (pending && (route[0] !== "List" || vis(".frappe-list"))) {
				pending = false;
				if (window.location.hash === "#tutorial") history.replaceState(null, "", window.location.pathname + window.location.search);
				setTimeout(() => current_tour()?.(), 300);
			}
		}, 250);
	}

	// the Payroll Entry list: by itself the first time an HR person opens it
	function first_payroll_list() {
		const route = frappe.get_route();
		if (route[0] !== "List" || route[1] !== "Payroll Entry" || pending || !is_hr() || seen("payroll_list")) return;
		let tries = 0;
		const wait = setInterval(() => {
			tries += 1;
			if (vis(".frappe-list") && button(__("Add Payroll Entry"))() || tries > 40) {
				clearInterval(wait);
				mark_seen("payroll_list");
				current_tour()?.();
			}
		}, 250);
	}

	frappe.router.on("change", () => {
		setTimeout(on_route, 300);
		setTimeout(first_payroll_list, 300);
	});
	$(document).on("app_ready", () => {
		setTimeout(on_route, 600);
		setTimeout(first_payroll_list, 600);
	});

	// "Tutorial" in a module's sidebar: the tour of the page you are on, else its link's list. The
	// desk opens every web-address item in a new tab, so the click is taken here.
	$(document).on("click", 'a[href*="#tutorial"]', (e) => {
		const href = e.currentTarget.getAttribute("href") || "";
		if (!/^\/desk\/[^#]+#tutorial$/.test(href)) return;
		e.preventDefault();
		e.stopImmediatePropagation();
		const play = current_tour();
		if (play) return play();
		pending = true;
		frappe.set_route(href.replace(/^\/desk\//, "").replace(/#tutorial$/, ""));
	});

	// --- registering -------------------------------------------------------------------------
	// Form tours get a Tutorial button after the form's own refresh (which may rebuild its buttons).
	// Payroll Entry's refresh clears every custom button on a submitted entry, so it calls
	// hrms_payroll_tour.add_button itself, last (payroll_entry.js).
	function add(tours) {
		for (const kind of Object.keys(TOURS)) Object.assign(TOURS[kind], tours[kind] || {});
		for (const dt of Object.keys(tours.form || {})) {
			if (dt === "Payroll Entry") continue;
			frappe.ui.form.on(dt, {
				refresh(frm) {
					setTimeout(() => frm.add_custom_button(__("Tutorial"), () => start(frm, TOURS.form[dt](frm))), 0);
				},
			});
		}
	}

	window.hrms_payroll_tour = {
		add_button(frm) {
			frm.add_custom_button(__("Tutorial"), () => start(frm, TOURS.form["Payroll Entry"](frm)));
			// the first Payroll Entry an HR person opens: the tour starts by itself, once
			if (is_hr() && !seen("payroll_form") && !running) {
				mark_seen("payroll_form");
				setTimeout(() => start(frm, TOURS.form["Payroll Entry"](frm)), 800);
			}
		},
	};

	window.hrms_tours = {
		add,
		start,
		builders: { list, form, report },
		h: { step, field, button, top, vis, shown, sidebar_link, card, list_rows, list_filters, add_button, again, report_table, report_menu },
	};
})();
