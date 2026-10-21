import { computed, ref } from "vue"

// The browser's install offer is kept here instead of popping up on every visit:
// people install from Profile → Install app when they want to.
const deferredPrompt = ref(null)
const installed = ref(
	window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true
)

window.addEventListener("beforeinstallprompt", (event) => {
	// keep the browser's own mini-infobar from showing; Profile offers the install instead
	event.preventDefault()
	deferredPrompt.value = event
})

window.addEventListener("appinstalled", () => {
	installed.value = true
	deferredPrompt.value = null
})

export const isIos = /iphone|ipad|ipod/.test(window.navigator.userAgent.toLowerCase())

export function useInstallApp() {
	// Chrome, Edge and Android offer an install prompt; iPhone needs Share → Add to Home Screen
	const canPrompt = computed(() => !installed.value && Boolean(deferredPrompt.value))
	const needsIosSteps = computed(() => !installed.value && isIos)

	async function install() {
		if (!deferredPrompt.value) return
		deferredPrompt.value.prompt()
		await deferredPrompt.value.userChoice
		deferredPrompt.value = null
	}

	return { canPrompt, needsIosSteps, install }
}
