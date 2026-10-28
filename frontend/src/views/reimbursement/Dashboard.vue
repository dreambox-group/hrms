<template>
	<BaseLayout :pageTitle="__('Reimbursement')">
		<template #actions>
			<router-link
				:to="{ name: 'ReimbursementNew' }"
				class="flex min-h-[40px] items-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
			>
				<FeatherIcon name="plus" class="h-4 w-4" />
				{{ __("New reimbursement") }}
			</router-link>
		</template>
		<template #body>
			<div class="flex w-full flex-col gap-4 px-4 pb-24 pt-5 lg:gap-5 lg:px-6">
				<p class="text-sm text-gray-700">
					{{ __("Paid for something for work? Send it here. Finance checks it in Drea Finance and pays it back to your account.") }}
				</p>

				<!-- status tabs: each one asks Drea Finance, so older claims are found too -->
				<div class="flex flex-row flex-wrap gap-2" role="tablist">
					<button
						v-for="tab in TABS"
						:key="tab.value"
						type="button"
						role="tab"
						:aria-selected="activeTab === tab.value"
						:class="[
							'min-h-[40px] rounded-xl px-3.5 text-sm font-semibold',
							activeTab === tab.value ? 'bg-ink text-white' : 'border border-line bg-white text-ink hover:bg-gray-50',
						]"
						@click="activeTab = tab.value"
					>
						{{ tab.label }}
					</button>
				</div>

				<div v-if="error" role="alert" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
					{{ error }}
				</div>

				<section class="flex flex-col rounded-2xl border border-line bg-white">
					<router-link
						v-for="row in rows"
						:key="row.id"
						:to="{ name: 'ReimbursementDetail', params: { id: row.id } }"
						class="flex flex-row items-center gap-3 border-b border-[#EEF0EE] px-4 py-3.5 last:border-0 hover:bg-gray-50"
					>
						<span class="flex min-w-0 flex-1 flex-col gap-0.5">
							<span class="truncate text-[15px] font-semibold text-ink">{{ row.description }}</span>
							<span class="text-[13px] text-gray-700">
								{{ row.code }} · {{ dayjs(row.expense_date).format("D MMM YYYY") }}{{ row.category ? ` · ${row.category}` : "" }}
							</span>
						</span>
						<span class="flex flex-col items-end gap-1">
							<span class="whitespace-nowrap text-[15px] font-bold text-ink">{{ formatCurrency(row.amount, "IDR") }}</span>
							<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[PROGRESS_TONE[row.progress.state]]]">
								{{ __(row.progress.word) }}
							</span>
						</span>
					</router-link>

					<div v-if="fetched && !loading && !rows.length" class="px-4 py-10 text-center text-sm text-gray-700">
						{{ activeTab === "all" ? __("No reimbursements yet.") : __("Nothing here.") }}
					</div>
					<div v-if="loading && !rows.length" class="px-4 py-10 text-center text-sm text-gray-700">{{ __("Loading…") }}</div>
				</section>

				<button
					v-if="hasMore"
					type="button"
					class="self-center rounded-xl border border-line bg-white px-5 py-2.5 text-sm font-semibold text-ink hover:bg-gray-50 disabled:opacity-50"
					:disabled="loading"
					@click="load(rows.length)"
				>
					{{ loading ? __("Loading…") : __("Load more") }}
				</button>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject, ref, watch } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { call, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { PROGRESS_TONE } from "@/data/reimbursements"
import { formatCurrency } from "@/utils/formatters"
import { TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const PAGE = 20
const TABS = [
	{ value: "all", label: __("All") },
	{ value: "waiting", label: __("Waiting") },
	{ value: "done", label: __("Approved or paid") },
	{ value: "stopped", label: __("Rejected or cancelled") },
]
const activeTab = ref("all")
const rows = ref([])
const hasMore = ref(false)
const loading = ref(false)
const fetched = ref(false)
const error = ref("")
let requestId = 0

async function load(start = 0) {
	const id = ++requestId
	loading.value = true
	error.value = ""
	try {
		const page = await call("hrms.api.reimbursements.get_my_reimbursements", {
			start,
			limit: PAGE,
			tab: activeTab.value === "all" ? null : activeTab.value,
		})
		if (id !== requestId) return
		rows.value = start ? rows.value.concat(page.items) : page.items
		hasMore.value = page.has_more
	} catch (err) {
		if (id !== requestId) return
		error.value = err.messages?.[0] || __("Your reimbursements could not be loaded.")
	} finally {
		if (id === requestId) {
			loading.value = false
			fetched.value = true
		}
	}
}
onIonViewWillEnter(() => load(0))
watch(activeTab, () => {
	rows.value = []
	load(0)
})
</script>
