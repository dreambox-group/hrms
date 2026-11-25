frappe.listview_settings["Salary Slip"] = {
	onload: function (listview) {
		if (
			!has_common(frappe.user_roles, [
				"Administrator",
				"System Manager",
				"HR Manager",
				"HR User",
			])
		)
			return;

		// owner, 24 Nov 2026: the ticked slips, or with none ticked every slip the filters show
		listview.page.add_menu_item(__("Export Salary Slips (CSV)"), () => {
			const args = {
				filters: JSON.stringify(listview.get_filters_for_args()),
				names: JSON.stringify(listview.get_checked_items(true)),
			};
			const method = "hrms.payroll.salary_slip_export";
			frappe.xcall(`${method}.count_salary_slips_for_export`, args).then((count) => {
				if (!count) {
					frappe.msgprint(
						__("No salary slips to export: none are ticked or match the list's filters."),
					);
					return;
				}
				const which = JSON.parse(args.names).length
					? __("the {0} ticked salary slips", [count])
					: __("the {0} salary slips matching the filters", [count]);
				frappe.confirm(
					__("Export {0} as a CSV file? Cancelled slips are left out.", [which]),
					() => open_url_post(`/api/method/${method}.export_salary_slips`, args),
				);
			});
		});

		listview.page.add_menu_item(__("Email Salary Slips"), () => {
			if (!listview.get_checked_items().length) {
				frappe.msgprint(__("Please select the salary slips to email"));
				return;
			}

			frappe.confirm(__("Are you sure you want to email the selected salary slips?"), () => {
				listview.call_for_selected_items(
					"hrms.payroll.doctype.salary_slip.salary_slip.enqueue_email_salary_slips",
				);
			});
		});
	},
};
