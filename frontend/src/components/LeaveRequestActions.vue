<template>
	<div v-if="doc?.name" class="flex flex-col gap-3 w-full">
		<!-- who decides and how far it is (approval by levels) -->
		<div v-if="doc.approvers?.length && !hideApprovers" class="flex flex-col gap-1.5">
			<div class="text-sm font-semibold text-gray-700">{{ __("Approvers") }}</div>
			<div
				v-for="row in doc.approvers"
				:key="row.name"
				class="flex flex-row justify-between items-center text-sm"
			>
				<span>
					{{ row.approver_name || row.approver }}
					<span class="text-gray-500">· {{ __(row.approval_level) }}</span>
				</span>
				<span :class="['rounded-full px-2 py-0.5 text-xs font-semibold', DECISION_CLASSES[row.decision]]">
					{{ __(row.decision) }}
				</span>
			</div>
		</div>

		<div v-if="attachments.data?.length" class="flex flex-col gap-1.5">
			<div class="text-sm font-semibold text-gray-700">{{ __("Attachments") }}</div>
			<AttachmentThumbnails :files="attachments.data" />
		</div>

		<!-- the supporting document can follow the request -->
		<div
			v-if="documentMissing"
			class="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900 flex flex-col gap-2"
		>
			<div>
				<span class="font-semibold">{{ __("Supporting document needed") }}</span>
				· {{ __("there is no deadline; the reminder stays until it is uploaded") }}
			</div>
			<LeaveDocumentUpload
				v-if="isOwnLeave"
				:leave-application="doc.name"
				@uploaded="attachments.reload()"
			/>
		</div>

		<LeaveDecisionButtons
			v-if="canDecide"
			:leave-application="doc.name"
			full-width
			@decided="(status) => emit('decided', status)"
		/>
		<div v-else-if="isOpen && !isOwnLeave" class="text-center text-sm text-gray-500">
			{{ __("Waiting for the other approvers.") }}
		</div>
	</div>
</template>

<script setup>
import { computed, inject, watch } from "vue"
import { createResource } from "frappe-ui"

import AttachmentThumbnails from "@/components/AttachmentThumbnails.vue"
import LeaveDecisionButtons from "@/components/LeaveDecisionButtons.vue"
import LeaveDocumentUpload from "@/components/LeaveDocumentUpload.vue"
import { settings } from "@/data/settings"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const user = inject("$user")
const employee = inject("$employee")

const props = defineProps({
	doc: { type: Object, default: null },
	// the leave detail shows the approvers in its own timeline
	hideApprovers: { type: Boolean, default: false },
})
const emit = defineEmits(["decided"])

const DECISION_CLASSES = {
	Approved: "bg-green-100 text-green-800",
	Rejected: "bg-red-100 text-red-800",
	Pending: "bg-gray-100 text-gray-700",
}
const HR_ROLES = ["HR Manager", "HR User", "System Manager"]

const attachments = createResource({ url: "hrms.api.get_attachments" })
watch(
	() => props.doc?.name,
	(name) => name && attachments.submit({ dt: "Leave Application", dn: name }),
	{ immediate: true }
)

const isOpen = computed(() => props.doc?.docstatus === 0 && props.doc?.status === "Open")
const isOwnLeave = computed(() => props.doc?.employee === employee?.data?.name)
const isHR = computed(() => (user?.data?.roles || []).some((role) => HR_ROLES.includes(role)))

const documentMissing = computed(
	() =>
		Boolean(props.doc?.document_required) &&
		props.doc?.docstatus !== 2 &&
		props.doc?.status !== "Rejected" &&
		attachments.fetched &&
		!attachments.data?.length
)

// approval by levels: the user's own pending vote; otherwise the chosen approver (or HR) decides
const canDecide = computed(() => {
	if (!isOpen.value || isOwnLeave.value) return false
	if (settings.data?.leave_approval_by_levels) {
		const approvers = props.doc.approvers || []
		const mine = approvers.find((row) => row.approver === user?.data?.name && row.decision === "Pending")
		if (!mine) return false
		const regularDecided = approvers.some(
			(row) => row.approval_level === "Regular" && row.decision !== "Pending"
		)
		return !(mine.approval_level === "Regular" && regularDecided)
	}
	return props.doc.leave_approver === user?.data?.name || isHR.value
})
</script>
