import { createResource } from "frappe-ui"

export const unreadNotificationsCount = createResource({
	url: "hrms.api.get_unread_notifications_count",
	cache: "hrms:unread_notifications_count",
	initialData: 0,
	auto: true,
})

// the user's own notifications, read by user: not every employee's roles grant PWA Notification
export const notifications = createResource({
	url: "hrms.api.employee_app.get_notifications",
	cache: "hrms:notifications",
	onSuccess() {
		unreadNotificationsCount.reload()
	},
})

export const markNotificationAsRead = createResource({
	url: "hrms.api.employee_app.mark_notification_as_read",
	onSuccess() {
		unreadNotificationsCount.reload()
	},
})

export const markAllNotificationsAsRead = createResource({
	url: "hrms.api.mark_all_notifications_as_read",
	onSuccess() {
		notifications.reload()
	},
})

export const arePushNotificationsEnabled = createResource({
	url: "hrms.api.are_push_notifications_enabled",
	cache: "hrms:push_notifications_enabled",
	auto: true,
})

// the page a notification points to, e.g. Leave Application → LeaveApplicationDetailView
export function notificationRoute(item) {
	if (!item.reference_document_type || !item.reference_document_name) return null
	return {
		name: `${item.reference_document_type.replace(/\s+/g, "")}DetailView`,
		params: { id: item.reference_document_name },
	}
}
