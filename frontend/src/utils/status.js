// One set of status colours for the whole app: green = fine, amber = waiting or late,
// red = rejected or absent, blue = on leave, grey = nothing to see
export const TONE_CLASSES = {
	ok: "bg-[#E2F4EA] text-[#0F6B4C]",
	warn: "bg-[#FDEFD6] text-[#8A4B00]",
	bad: "bg-[#FCE6E4] text-[#A8231A]",
	info: "bg-[#E4ECFB] text-[#1E55B8]",
	neutral: "bg-[#EEF0EE] text-[#4B525A]",
}

export const TONE_DOTS = {
	ok: "bg-[#0F6B4C]",
	warn: "bg-[#B86200]",
	bad: "bg-[#A8231A]",
	info: "bg-[#1E55B8]",
	neutral: "bg-[#8A9098]",
}

export const LEAVE_STATUS_TONE = {
	Open: "warn",
	Approved: "ok",
	Rejected: "bad",
	Cancelled: "neutral",
}

// "Open" reads as waiting to the employee
export const LEAVE_STATUS_LABEL = {
	Open: "Waiting",
	Approved: "Approved",
	Rejected: "Rejected",
	Cancelled: "Cancelled",
}

const AVATAR_COLOURS = ["#DDF5EA", "#E4ECFB", "#FDEFD6", "#FCE8F1", "#EDE7FB", "#E6F2F6"]

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
