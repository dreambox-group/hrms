// Device-specific steps for when the camera or location is blocked or switched off.
// Browsers don't let a page re-enable a blocked permission itself, so the person is told where to tap.

const userAgent = window.navigator.userAgent

export const device =
	/iPhone|iPad|iPod/.test(userAgent) || (/Macintosh/.test(userAgent) && navigator.maxTouchPoints > 1)
		? "ios"
		: /Android/.test(userAgent)
		? "android"
		: "computer"

export const getBlockedHelp = (__, kind) =>
	({
		camera: {
			ios: __(
				"Open the Settings app → Apps → Safari → Camera → Allow (or in Safari tap “aA” → Website Settings → Camera → Allow), then tap Try again."
			),
			android: __(
				"Tap the icon on the left of the address bar → Permissions → Camera → Allow, then tap Try again."
			),
			computer: __(
				"Click the icon on the left of the address bar → Site settings → Camera → Allow, then click Try again. On Windows also check Settings → Privacy & security → Camera."
			),
		},
		location: {
			ios: __(
				"Open the Settings app → Privacy & Security → Location Services: turn it on, and set Safari Websites to “While Using the App”. Then tap Try again."
			),
			android: __(
				"Tap the icon on the left of the address bar → Permissions → Location → Allow, then tap Try again."
			),
			computer: __(
				"Click the icon on the left of the address bar → Site settings → Location → Allow, then click Try again. On Windows also check Settings → Privacy & security → Location."
			),
		},
	})[kind][device]

export const getLocationOffHelp = (__) =>
	device === "computer"
		? __(
				"This computer could not work out its location. Turn on location in your computer's settings (on Windows: Settings → Privacy & security → Location), then click Try again."
		  )
		: __("Your phone's location (GPS) is turned off. Turn on Location in your quick settings, then tap Try again.")

// "granted", "denied", "prompt" or null where the browser can't tell (e.g. Firefox for the camera)
export async function watchPermission(name, onChange) {
	if (!navigator.permissions?.query) return null
	try {
		const status = await navigator.permissions.query({ name })
		status.onchange = () => onChange?.(status.state)
		return status.state
	} catch (e) {
		return null
	}
}
