<template>
	<div v-if="doc" class="flex flex-col gap-4">
		<div class="flex flex-row items-start justify-between gap-3">
			<div>
				<h2 class="text-lg font-bold text-ink">{{ doc.leave_type }}</h2>
				<div v-if="!isOwnLeave" class="mt-0.5 text-sm text-gray-700">{{ doc.employee_name }}</div>
			</div>
			<span :class="['whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[tone]]">
				{{ __(LEAVE_STATUS_LABEL[status] || status) }}
			</span>
		</div>

		<div class="flex flex-col gap-2.5 text-sm">
			<div class="flex flex-row justify-between gap-3">
				<span class="text-gray-700">{{ __("Dates") }}</span>
				<span class="text-right font-semibold text-ink">{{ dates }}</span>
			</div>
			<div class="flex flex-row justify-between gap-3">
				<span class="text-gray-700">{{ __("Days") }}</span>
				<span class="font-semibold text-ink">{{ doc.total_leave_days }}</span>
			</div>
			<div v-if="doc.leave_balance != null" class="flex flex-row justify-between gap-3">
				<span class="text-gray-700">{{ __("Balance when requested") }}</span>
				<span class="font-semibold text-ink">{{ doc.leave_balance }}</span>
			</div>
			<div v-if="doc.description" class="rounded-xl bg-page px-3.5 py-2.5 text-ink whitespace-pre-line">“{{ doc.description }}”</div>
		</div>

		<!-- what happened, in order -->
		<ol class="flex flex-col">
			<li v-for="(step, index) in steps" :key="index" class="flex flex-row gap-3">
				<div class="flex flex-col items-center">
					<span :class="['mt-1 h-3 w-3 rounded-full', step.dot]"></span>
					<span v-if="index < steps.length - 1" class="min-h-[18px] w-0.5 flex-1 bg-line"></span>
				</div>
				<div class="pb-3.5">
					<div class="text-sm font-semibold text-ink">{{ step.what }}</div>
					<div v-if="step.when" class="text-[13px] text-gray-700">{{ step.when }}</div>
				</div>
			</li>
		</ol>

		<LeaveRequestActions :doc="doc" hide-approvers @decided="emit('changed')" />

		<a
			v-if="isHR"
			:href="`/app/leave-application/${doc.name}`"
			class="self-start text-sm font-medium text-brand-600 hover:text-brand-700"
		>
			{{ __("Open in the desk to correct it") }}
		</a>
	</div>
	<div v-else-if="resource.loading" class="py-6 text-center text-sm text-gray-700">{{ __("Loading…") }}</div>
</template>

<script setup>
import { computed, inject, watch } from "vue"
import { createResource } from "frappe-ui"

import LeaveRequestActions from "@/components/LeaveRequestActions.vue"
import { LEAVE_STATUS_LABEL, LEAVE_STATUS_TONE, TONE_CLASSES } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const user = inject("$user")
const employee = inject("$employee")

const props = defineProps({ name: { type: String, required: true } })
const emit = defineEmits(["changed"])

const resource = createResource({ url: "frappe.client.get" })
watch(
	() => props.name,
	(name) => name && resource.submit({ doctype: "Leave Application", name }),
	{ immediate: true }
)

const doc = computed(() => resource.data)
const status = computed(() => (doc.value?.docstatus === 2 ? "Cancelled" : doc.value?.status))
const tone = computed(() => LEAVE_STATUS_TONE[status.value] || "neutral")
const isOwnLeave = computed(() => doc.value?.employee === employee?.data?.name)
const isHR = computed(() =>
	(user?.data?.roles || []).some((role) => ["HR Manager", "HR User", "System Manager"].includes(role))
)

const dates = computed(() => {
	if (!doc.value) return ""
	const from = dayjs(doc.value.from_date).format("ddd D MMM YYYY")
	return doc.value.from_date === doc.value.to_date ? from : `${from} – ${dayjs(doc.value.to_date).format("ddd D MMM YYYY")}`
})

const when = (value) => (value ? dayjs(value).format("ddd D MMM, HH:mm") : "")

const steps = computed(() => {
	const d = doc.value
	if (!d) return []
	const list = [
		{ what: isOwnLeave.value ? __("You sent the request") : __("{0} sent the request", [d.employee_name]), when: when(d.creation), dot: "bg-ink" },
	]
	if (d.approvers?.length) {
		for (const row of d.approvers) {
			const who = row.approver_name || row.approver
			if (row.decision === "Approved") list.push({ what: __("Approved by {0}", [who]), when: when(row.decided_on), dot: "bg-[#0F6B4C]" })
			else if (row.decision === "Rejected") list.push({ what: __("Rejected by {0}", [who]), when: when(row.decided_on), dot: "bg-[#A8231A]" })
			else if (d.status === "Open") list.push({ what: __("Waiting for {0}", [who]), when: "", dot: "bg-[#B86200]" })
		}
	} else if (d.status === "Approved" || d.status === "Rejected") {
		const who = d.leave_approver_name || d.leave_approver || __("the approver")
		list.push({
			what: d.status === "Approved" ? __("Approved by {0}", [who]) : __("Rejected by {0}", [who]),
			when: when(d.modified),
			dot: d.status === "Approved" ? "bg-[#0F6B4C]" : "bg-[#A8231A]",
		})
	} else if (d.status === "Open") {
		list.push({ what: __("Waiting for {0}", [d.leave_approver_name || __("the approver")]), when: "", dot: "bg-[#B86200]" })
	}
	if (d.docstatus === 2) list.push({ what: __("Cancelled"), when: when(d.modified), dot: "bg-gray-400" })
	return list
})
</script>
