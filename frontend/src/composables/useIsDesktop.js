import { onBeforeUnmount, ref } from "vue"

// wide screens get side panels and drop-downs; phones keep full pages and bottom sheets
const query = typeof window !== "undefined" ? window.matchMedia("(min-width: 1024px)") : null

export function useIsDesktop() {
	const isDesktop = ref(Boolean(query?.matches))
	const update = (event) => (isDesktop.value = event.matches)
	query?.addEventListener("change", update)
	onBeforeUnmount(() => query?.removeEventListener("change", update))
	return isDesktop
}
