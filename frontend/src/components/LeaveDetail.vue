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

		<!-- the employee's own approved leave: ask HR to change or cancel it -->
		<template v-if="isOwnLeave && doc.docstatus === 1 && doc.status === 'Approved'">
			<div v-if="openChange" class="flex flex-col gap-2 rounded-xl bg-[#FDEFD6] px-3.5 py-3 text-sm text-[#8A4B00]">
				<div>
					<span class="font-semibold">{{ __("Waiting for HR") }}</span>
					· {{ changeLabel(openChange) }}
				</div>
				<button
					type="button"
					class="self-start text-[13px] font-semibold underline"
					:disabled="withdraw.loading"
					@click="withdrawChange(openChange.name)"
				>
					{{ __("Withdraw this request") }}
				</button>
			</div>
			<LeaveChangeForm v-else-if="changeFormOpen" :doc="doc" @close="changeFormOpen = false" @sent="changeSent" />
			<button
				v-else
				type="button"
				class="flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-line px-4 text-[15px] font-semibold text-ink hover:bg-gray-50"
				@click="changeFormOpen = true"
			>
				<FeatherIcon name="edit-2" class="h-4 w-4" />
				{{ __("Change or cancel this leave") }}
			</button>
		</template>

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
import { computed, inject, ref, watch } from "vue"
import { createResource, FeatherIcon, toast } from "frappe-ui"

import LeaveChangeForm from "@/components/LeaveChangeForm.vue"
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

// requests to change or cancel this leave (and the one that gave it new dates)
const changes = createResource({ url: "hrms.api.employee_app.get_my_leave_changes" })
const changeFormOpen = ref(false)
watch(
	() => [props.name, doc.value?.employee],
	([name]) => {
		changeFormOpen.value = false
		if (name && isOwnLeave.value) changes.submit({ leave_application: name })
	},
	{ immediate: true }
)
const openChange = computed(() =>
	(changes.data || []).find((row) => row.status === "Open" && row.leave_application === props.name)
)
function changeLabel(row) {
	return row.change === "Cancel the leave"
		? __("you asked to cancel this leave")
		: __("you asked to move it to {0}", [range(row.new_from_date, row.new_to_date)])
}
function changeSent() {
	changeFormOpen.value = false
	changes.reload()
	emit("changed")
}
const withdraw = createResource({ url: "hrms.api.employee_app.withdraw_leave_change" })
function withdrawChange(name) {
	withdraw.submit(
		{ name },
		{
			onSuccess: () => changes.reload(),
			onError(error) {
				toast({
					title: __("Error"),
					text: error.messages?.[0] || __("The request could not be withdrawn."),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}
const range = (from, to) => {
	const start = dayjs(from).format("ddd D MMM YYYY")
	return from === to ? start : `${start} – ${dayjs(to).format("ddd D MMM YYYY")}`
}
const dates = computed(() => (doc.value ? range(doc.value.from_date, doc.value.to_date) : ""))

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
	// HR's decisions on change requests: the one that gave this leave its dates, or any about it
	for (const row of [...(changes.data || [])].reverse()) {
		if (row.new_leave_application === d.name)
			list.push({
				what: __("HR moved it here from {0}", [range(row.from_date, row.to_date)]),
				when: when(row.decided_on),
				dot: "bg-[#1E55B8]",
			})
		else if (row.leave_application === d.name && row.status !== "Open") {
			const asked = row.change === "Cancel the leave" ? __("cancel it") : __("move it to {0}", [range(row.new_from_date, row.new_to_date)])
			list.push({
				what: row.status === "Approved" ? __("HR approved your request to {0}", [asked]) : __("HR rejected your request to {0}", [asked]),
				when: [when(row.decided_on), row.hr_note].filter(Boolean).join(" · "),
				dot: row.status === "Approved" ? "bg-[#0F6B4C]" : "bg-[#A8231A]",
			})
		}
	}
	if (d.docstatus === 2) list.push({ what: __("Cancelled"), when: when(d.modified), dot: "bg-gray-400" })
	return list
})
</script>
