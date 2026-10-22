import { ref } from "vue"

// wide screens open the leave request as a side panel over the current page (App.vue);
// phones go to its own page
export const leaveRequestOpen = ref(false)

export function openLeaveRequest(router, isDesktop) {
	if (isDesktop) leaveRequestOpen.value = true
	else router.push({ name: "LeaveApplicationFormView" })
}
