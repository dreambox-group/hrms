// Drea Design System, "When something breaks" (owner, 25 Nov 2026): never show code, error
// numbers or stack traces to users. Frappe's "Server Error" dialog prints the database error;
// this replaces it with a calm message. The details stay in the server log, and "Copy details"
// puts them on the clipboard for the developers without showing them.
// Loaded as a plain file (hooks.app_include_js), after the desk bundle defines frappe.request.
(function () {
	if (!frappe.request || frappe.request.__drea_errors) return;

	function parse(xhr) {
		try {
			return JSON.parse(xhr.responseText) || {};
		} catch (e) {
			return {};
		}
	}

	function details(xhr, data) {
		let exc = data.exc || "";
		try {
			exc = (JSON.parse(exc) || []).join("\n");
		} catch (e) {
			// already plain text
		}
		return [
			"Route: " + frappe.get_route_str(),
			"Request ID: " + (xhr.getResponseHeader("X-Frappe-Request-Id") || "-"),
			"Versions: " + JSON.stringify(frappe.boot.versions),
			"",
			exc,
		].join("\n");
	}

	frappe.request.report_error = function (xhr) {
		const data = parse(xhr);
		// Frappe showed nothing at all when the server keeps the details back (Allow Error
		// Traceback off, as on the live site); now the user is told. When the server already
		// sent its own message, that message was shown, so stay quiet.
		if (!data.exc && data._server_messages) return;

		if (!frappe.drea_error_dialog) {
			frappe.drea_error_dialog = new frappe.ui.Dialog({
				title: __("This did not work"),
				primary_action_label: __("Close"),
				primary_action: () => frappe.drea_error_dialog.hide(),
				secondary_action_label: __("Copy details"),
			});
			frappe.drea_error_dialog.wrapper.classList.add("msgprint-dialog");
		}
		const dialog = frappe.drea_error_dialog;
		dialog.set_secondary_action(() => {
			frappe.utils.copy_to_clipboard(details(xhr, data));
		});
		dialog.$body.html(
			`<p>${__("Something on this page did not load or save.")}</p>
			<p class="text-muted">${__("What you typed is still here. Try again in a moment.")}</p>
			<p class="text-muted">${__(
				"If it keeps happening, tell your Drea HR admin. Copy details gives them what they need."
			)}</p>`
		);
		dialog.show();
	};

	frappe.request.__drea_errors = true;
})();
