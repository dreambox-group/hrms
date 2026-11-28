// The six status tones of the Drea Design System (v0.8), always shown with a word:
// ok = Done (finished well), warn = Waiting (for someone), bad = Problem (stopped),
// info = Decided (decided, or on leave), neutral = not started, over = ended, nothing more to do
export const TONE_CLASSES = {
	ok: "bg-[#D6EBDF] text-[#005A2D]",
	warn: "bg-[#FFF8DB] text-[#7A5500]",
	bad: "bg-[#FDEFF1] text-[#8F2A38]",
	info: "bg-[#F0F7FF] text-[#004C94]",
	neutral: "bg-[#ECEDF5] text-[#323338]",
	over: "bg-[#D0D4E4] text-[#535463]",
}

export const TONE_DOTS = {
	ok: "bg-[#00854D]",
	warn: "bg-[#EAAA15]",
	bad: "bg-[#B63546]",
	info: "bg-[#0060B9]",
	neutral: "bg-[#9699A6]",
	over: "bg-[#9699A6]",
}

export const LEAVE_STATUS_TONE = {
	Open: "warn",
	Approved: "info",
	Rejected: "bad",
	Cancelled: "over",
}

// "Open" reads as waiting to the employee
export const LEAVE_STATUS_LABEL = {
	Open: "Waiting",
	Approved: "Approved",
	Rejected: "Rejected",
	Cancelled: "Cancelled",
}

// initials sit on light blue (design system: avatar = photo, or initials on blue)
const AVATAR_COLOURS = ["#CCE5FF"]

export function avatarColour(name = "") {
	const sum = [...name].reduce((total, char) => total + char.charCodeAt(0), 0)
	return AVATAR_COLOURS[sum % AVATAR_COLOURS.length]
}

export function initials(name = "") {
	return name
		.split(" ")
		.filter(Boolean)
		.slice(0, 2)
		.map((word) => word[0].toUpperCase())
		.join("")
}
