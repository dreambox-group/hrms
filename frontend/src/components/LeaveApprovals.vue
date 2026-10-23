<template>
	<div v-if="!rows.length" class="text-sm text-gray-500 py-3">
		{{ __("Nothing is waiting for your approval.") }}
	</div>

	<!-- one card per request: two columns on wide screens, stacked on phones -->
	<div v-else :class="['grid gap-3', layout === 'table' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1']">
		<div
			v-for="row in rows"
			:key="row.name"
			class="rounded-lg border bg-white p-4 flex flex-col gap-2 cursor-pointer hover:border-gray-400"
			@click="open(row)"
		>
			<div class="flex flex-row justify-between gap-3">
				<div>
					<div class="font-semibold text-gray-900">{{ row.employee_name }}</div>
					<div class="text-xs text-gray-500">{{ row.department }}</div>
				</div>
				<span class="text-sm text-gray-700 text-right">{{ row.label }}</span>
			</div>

			<div class="text-sm text-gray-900">
				{{ dates(row) }} · {{ __("{0} days", [row.total_leave_days]) }}
			</div>

			<div v-if="row.description" class="text-sm text-gray-700 whitespace-pre-line line-clamp-3">
				{{ row.description }}
			</div>

			<AttachmentThumbnails :files="row.attachments" />
			<div
				v-if="row.document_missing"
				class="self-start rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-orange-800"
			>
				{{ __("Document not uploaded yet") }}
			</div>

			<div class="flex flex-row flex-wrap items-end justify-between gap-3 mt-1">
				<div class="text-xs text-gray-500">
					<div v-for="line in row.progress" :key="line">{{ line }}</div>
				</div>
				<LeaveDecisionButtons :leave-application="row.name" class="ml-auto" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRouter } from "vue-router"

import AttachmentThumbnails from "@/components/AttachmentThumbnails.vue"
import LeaveDecisionButtons from "@/components/LeaveDecisionButtons.vue"
import { homeData } from "@/data/home"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

defineProps({ layout: { type: String, default: "table" } })

const rows = computed(() => homeData.data?.leave_approvals || [])

function dates(row) {
	const from = dayjs(row.from_date).format("D MMM")
	return row.from_date === row.to_date ? from : `${from} – ${dayjs(row.to_date).format("D MMM")}`
}

// the card opens the request; the buttons and thumbnails act without opening it
function open(row) {
	router.push({ name: "LeaveApplicationDetailView", params: { id: row.name } })
}
</script>
