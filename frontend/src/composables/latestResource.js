import { reactive } from "vue"
import { call } from "frappe-ui"

// Like createResource, but only the answer to the newest request is kept: when the user moves a
// week or month, or picks another person, before an older request answers, that older answer is
// dropped instead of overwriting the newer one.
export function latestResource({ url, makeParams, auto = false }) {
	let requestId = 0
	const resource = reactive({
		data: null,
		params: null,
		loading: false,
		fetched: false,
		error: null,
		async submit(params) {
			const id = ++requestId
			resource.params = params
			resource.loading = true
			try {
				const data = await call(url, params)
				if (id !== requestId) return
				resource.data = data
				resource.error = null
				return data
			} catch (error) {
				if (id !== requestId) return
				resource.error = error
			} finally {
				if (id === requestId) {
					resource.loading = false
					resource.fetched = true
				}
			}
		},
		reload() {
			return resource.submit(makeParams ? makeParams() : resource.params)
		},
	})
	if (auto) resource.reload()
	return resource
}
