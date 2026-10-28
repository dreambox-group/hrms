<template>
	<section :aria-label="__('Team leave history')" class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:p-6">
		<div class="flex flex-row flex-wrap items-start justify-between gap-3">
			<div>
				<h2 class="text-base font-bold text-ink lg:text-lg">{{ __("Team leave history") }}</h2>
				<p class="text-[13px] text-gray-700">{{ __("Everyone whose leave you approve") }}</p>
			</div>
			<select
				v-model="person"
				:aria-label="__('Person')"
				class="min-h-[40px] rounded-xl border border-[#D5DAD4] bg-white px-3 text-sm text-ink focus:border-brand-600 focus:ring-brand-600"
			>
				<option value="">{{ __("Everyone") }}</option>
				<option v-for="row in history.data?.employees || []" :key="row.employee" :value="row.employee">
					{{ row.employee_name }}
				</option>
			</select>
		</div>

		<div role="tablist" :aria-label="__('Filter')" class="flex flex-row gap-1 overflow-x-auto rounded-xl bg-[#F1F3F0] p-1">
			<button
				v-for="tab in TABS"
				:key="tab.value"
				type="button"
				role="tab"
				:aria-selected="status === tab.value"
				:class="[
					'min-h-[36px] whitespace-nowrap rounded-lg px-3.5 text-sm',
					status === tab.value ? 'bg-white font-semibold text-ink shadow-sm' : 'font-medium text-gray-700',
				]"
				@click="status = tab.value"
			>
				{{ tab.label }}
			</button>
		</div>

		<div v-for="row in shown" :key="row.name" class="border-t border-[#EEF0EE] pt-3">
			<button
				type="button"
				class="flex w-full flex-row items-center gap-3 text-left"
				:aria-expanded="open === row.name"
				@click="open = open === row.name ? null : row.name"
			>
				<span
					class="flex h-9 w-9 flex-none items-center justify-center rounded-full text-xs font-semibold text-ink"
					:style="{ background: avatarColour(row.employee_name) }"
				>
					{{ initials(row.employee_name) }}
				</span>
				<span class="flex min-w-0 flex-1 flex-col gap-0.5">
					<span class="truncate text-sm font-semibold text-ink">{{ row.employee_name }} · {{ row.label || row.leave_type }}</span>
					<span class="text-[13px] text-gray-700">{{ dates(row) }}</span>
				</span>
				<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[LEAVE_STATUS_TONE[row.status] || 'neutral']]">
					{{ __(LEAVE_STATUS_LABEL[row.status] || row.status) }}
				</span>
			</button>
			<div v-if="open === row.name" class="ml-12 mt-2 flex flex-col gap-1.5 text-[13px] text-gray-700">
				<div v-if="row.description" class="rounded-xl bg-page px-3 py-2 text-ink whitespace-pre-line">“{{ row.description }}”</div>
				<div v-for="approver in row.approvers" :key="approver.approver + approver.approval_level">
					{{ approver.approver_name || approver.approver }} · {{ __(approver.decision === "Pending" ? "Waiting" : approver.decision) }}
				</div>
				<div v-if="!row.approvers.length && row.leave_approver_name">{{ __("Approver: {0}", [row.leave_approver_name]) }}</div>
				<div v-if="row.amended_from">{{ __("Dates changed by HR") }}</div>
			</div>
		</div>

		<div v-if="history.fetched && !rows.length" class="rounded-xl border border-dashed border-[#D5DAD4] p-5 text-center text-sm text-gray-700">
			{{ __("No leave here.") }}
		</div>
		<button v-if="rows.length > shown.length || showAll" type="button" class="self-start pt-1 text-sm font-semibold text-brand-600" @click="showAll = !showAll">
			{{ showAll ? __("Show less") : __("Show all ({0})", [rows.length]) }}
		</button>
	</section>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { createResource } from "frappe-ui"

import { avatarColour, initials, LEAVE_STATUS_LABEL, LEAVE_STATUS_TONE, TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const TABS = [
	{ value: "", label: __("All") },
	{ value: "Open", label: __("Waiting") },
	{ value: "Approved", label: __("Approved") },
	{ value: "Rejected", label: __("Rejected") },
	{ value: "Cancelled", label: __("Cancelled") },
]
const person = ref("")
const status = ref("")
const open = ref(null)
const showAll = ref(false)

// the person and status are filtered on the server, so older requests are found too
const history = createResource({
	url: "hrms.api.employee_app.get_team_leave_history",
	makeParams: () => ({ employee: person.value || null, status: status.value || null, limit: 300 }),
	auto: true,
})
onIonViewWillEnter(() => history.reload())
watch([person, status], () => {
	showAll.value = false
	history.reload()
})

// the answer for the current person and status only (an older, slower answer is ignored)
const rows = computed(() =>
	(history.data?.requests || []).filter(
		(row) => (!person.value || row.employee === person.value) && (!status.value || row.status === status.value)
	)
)
const shown = computed(() => (showAll.value ? rows.value : rows.value.slice(0, 6)))

function dates(row) {
	const from = dayjs(row.from_date).format("ddd D MMM YYYY")
	const range = row.from_date === row.to_date ? from : `${from} – ${dayjs(row.to_date).format("ddd D MMM YYYY")}`
	return `${range} · ${row.total_leave_days == 1 ? __("1 day") : __("{0} days", [row.total_leave_days])}`
}
</script>
