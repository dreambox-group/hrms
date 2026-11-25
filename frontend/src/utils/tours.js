// Drea One tutorials (owner, 24 Nov 2026), with driver.js (MIT), the library the HR desk's
// tutorials use. The "?" button in the top bar (BaseLayout) plays the tour of the screen you are on;
// nothing starts by itself. Steps point at elements marked data-tour="…"; a marked element that is
// not on screen (a card that is hidden for you, a desktop-only part on a phone) is skipped, and a
// step without an element shows in the middle.
import { driver } from "driver.js"
import "driver.js/dist/driver.css"

// Ionic keeps earlier screens in the page, hidden: only an element on the screen now counts
const onScreen = (el) => el && el.getClientRects().length > 0 && !el.closest(".ion-page-hidden")
const find = (key) => [...document.querySelectorAll(`[data-tour="${key}"]`)].find(onScreen)

// [key or null, title, text]: a key whose element is not on screen drops the step
const STEPS = (__) => ({
	Home: [
		[null, __("Welcome to Drea One"), __("Your HR in one place: check in, ask for leave, see your schedule and your salary. This tour shows the Home screen.")],
		["nav", __("Sections"), __("Attendance, Leaves, Employee Schedule and Salary. On a phone they are at the bottom.")],
		["tabs", __("Sections"), __("Attendance, Leaves, Employee Schedule and Salary.")],
		["checkin", __("Check in"), __("Check in when you start work and out when you finish. The app asks for your location and a selfie. Away from the office? Pick a reason; your supervisor sees it.")],
		["todo", __("To do"), __("What is waiting for you: requests to approve if you are a supervisor, or a document to upload.")],
		["team", __("Team today"), __("Who in your team is in, late, on leave or not checked in yet.")],
		["leave", __("Your leave"), __("Days left and your next leave. Ask for leave from here.")],
		["period", __("This pay period"), __("Late days, unpaid leave and days without check-in so far this pay period: these are deducted from this month's pay.")],
		["around", __("Around the office"), __("Who is out today, birthdays and the next holiday.")],
		["requests", __("My requests"), __("Your latest requests and whether they are approved.")],
		["bell", __("Notifications"), __("Approvals, decisions and reminders.")],
		["profile", __("Profile"), __("Your details, your password and the app's settings.")],
		["help", __("Need this again?"), __("This button explains the screen you are on, on every screen.")],
	],
	AttendanceDashboard: [
		[null, __("Attendance"), __("Your month at a glance: when you checked in, late days, leave and holidays.")],
		["calendar", __("Your month"), __("Each day's status. Tap a day to see its check-ins; the arrows change the month.")],
		["schedule", __("Your schedule"), __("Your shift and office.")],
		["attendance-requests", __("Requests"), __("Ask to count days as work from home or on duty, or to work another shift.")],
		["history", __("Check-in history"), __("Every check-in and check-out you made.")],
		["team-attendance", __("Your team"), __("For supervisors: your team's month. Pick someone to see their days.")],
		["help", __("Need this again?"), __("This button explains the screen you are on.")],
	],
	LeavesDashboard: [
		[null, __("Leaves"), __("Your leave days, your requests and the holidays.")],
		["request-leave", __("Request leave"), __("Pick the type, the dates and a reason. Your supervisors decide; you get a notification.")],
		["end-date", __("Contract end date"), __("Your leave moves your contract end date: each leave day adds a working day.")],
		["balances", __("Your days"), __("Per leave type: used and left this period.")],
		["my-requests", __("My requests"), __("Every request and its status. Open one to see it, cancel it or ask for a change.")],
		["cuti-pengganti", __("Overtime Submission"), __("Worked on a holiday? Send it here; once approved you get the same days off (Cuti Pengganti).")],
		["holidays", __("Upcoming holidays"), __("The next days off.")],
		["help", __("Need this again?"), __("This button explains the screen you are on.")],
	],
	Roster: [
		[null, __("Employee Schedule"), __("Who works which shift, when and where, for everyone.")],
		["week", __("The week"), __("Move to the previous or next week.")],
		["schedule-table", __("The schedule"), __("One row per person, one column per day.")],
		["help", __("Need this again?"), __("This button explains the screen you are on.")],
	],
	SalarySlipsDashboard: [
		[null, __("Salary"), __("Your salary slips, one per month. Only you (and HR) can see them.")],
		["slips", __("Your slips"), __("Open one for its earnings, deductions and take-home pay, and to download it.")],
		["amounts", __("Hide amounts"), __("Hide or show the amounts, for example in public.")],
		["help", __("Need this again?"), __("This button explains the screen you are on.")],
	],
	Approvals: [
		[null, __("To do"), __("Everything waiting for you: leave, Overtime Submissions and outside-office check-ins of your team, and your own reminders.")],
		["todo", __("Decide"), __("Open a request to approve or reject it. Your team member gets a notification.")],
		["help", __("Need this again?"), __("This button explains the screen you are on.")],
	],
})

export const hasTour = (routeName) => Boolean(STEPS((s) => s)[routeName])

let active = null
export function startTour(routeName, __) {
	const steps = (STEPS(__)[routeName] || [])
		.map(([key, title, description]) => {
			if (!key) return { popover: { title, description } }
			const el = find(key)
			return el ? { element: el, popover: { title, description } } : null
		})
		.filter(Boolean)
	if (!steps.length || active) return
	active = driver({
		showProgress: true,
		allowClose: true,
		smoothScroll: true,
		nextBtnText: __("Next"),
		prevBtnText: __("Back"),
		doneBtnText: __("Done"),
		progressText: __("{{current}} of {{total}}"),
		steps,
		onDestroyed: () => {
			active = null
		},
	})
	active.drive()
}
