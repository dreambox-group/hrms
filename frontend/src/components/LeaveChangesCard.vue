<template>
	<section
		v-if="changes.data?.length"
		:aria-label="__('Change requests')"
		class="flex flex-col gap-1 rounded-2xl border border-line bg-white p-4 lg:p-6"
	>
		<h2 class="pb-2 text-base font-bold text-ink lg:text-lg">{{ __("Change requests") }}</h2>
		<div
			v-for="row in showAll ? changes.data : changes.data.slice(0, 5)"
			:key="row.name"
			class="flex flex-col gap-1 border-t border-[#EEF0EE] py-2.5"
		>
			<div class="flex flex-row items-start justify-between gap-3">
				<span class="text-sm font-semibold text-ink">{{ row.leave_type }} · {{ range(row.from_date, row.to_date) }}</span>
				<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[TONE[row.status]]]">
					{{ row.status === "Open" ? __("Waiting for HR") : __(row.status) }}
				</span>
			</div>
			<span class="text-[13px] text-gray-700">
				{{ row.change === "Cancel the leave" ? __("Cancel the leave") : __("Move to {0}", [range(row.new_from_date, row.new_to_date)]) }}
			</span>
			<span v-if="row.hr_note" class="text-[13px] text-gray-700">{{ __("HR: {0}", [row.hr_note]) }}</span>
		</div>
		<button
			v-if="changes.data.length > 5"
			type="button"
			class="self-start pt-1 text-sm font-semibold text-brand-600"
			@click="showAll = !showAll"
		>
			{{ showAll ? __("Show less") : __("Show all ({0})", [changes.data.length]) }}
		</button>
	</section>
</template>

<script setup>
import { inject, ref } from "vue"
import { onIonViewWillEnter } from "@ionic/vue"
import { createResource } from "frappe-ui"

import { TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const TONE = { Open: "warn", Approved: "ok", Rejected: "bad" }
const showAll = ref(false)

const changes = createResource({ url: "hrms.api.employee_app.get_my_leave_changes", auto: true })
onIonViewWillEnter(() => changes.reload())
defineExpose({ reload: () => changes.reload() })

function range(from, to) {
	const start = dayjs(from).format("D MMM")
	return from === to ? start : `${start} – ${dayjs(to).format("D MMM")}`
}
</script>
