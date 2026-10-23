<template>
	<section :aria-label="__('To do')" class="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 lg:gap-4 lg:p-6">
		<div class="flex flex-row items-center justify-between">
			<div class="flex flex-row items-center gap-2.5">
				<h3 class="text-base font-bold text-ink lg:text-lg">{{ __("To do") }}</h3>
				<span
					v-if="items.length"
					class="flex h-[22px] min-w-[22px] items-center justify-center rounded-full bg-[#C4321F] px-1.5 text-xs font-bold text-white"
				>
					{{ items.length }}
				</span>
			</div>
			<router-link
				v-if="limit && items.length > limit"
				:to="{ name: 'Approvals' }"
				class="text-sm font-semibold text-brand-600"
			>
				{{ __("See all") }}
			</router-link>
		</div>

		<div
			v-for="item in shown"
			:key="item.key"
			class="flex cursor-pointer flex-col gap-3 rounded-xl border border-line p-3.5 hover:border-gray-400 lg:flex-row lg:flex-wrap lg:items-center lg:gap-4 lg:p-4"
			@click="item.open && item.open()"
		>
			<div class="flex min-w-0 flex-1 flex-row gap-3 lg:basis-[280px]">
				<span
					class="flex h-10 w-10 flex-none items-center justify-center rounded-full text-[13px] font-semibold text-ink"
					:style="{ background: item.avatar }"
				>
					{{ item.initials }}
				</span>
				<div class="flex min-w-0 flex-col gap-0.5">
					<div class="flex flex-row flex-wrap items-center gap-2">
						<span class="text-[15px] font-semibold text-ink">{{ item.who }}</span>
						<span :class="['rounded-full px-2 py-0.5 text-xs font-semibold', TONE_CLASSES[item.tone]]">
							{{ item.kind }}
						</span>
					</div>
					<span class="text-sm text-ink">{{ item.title }}</span>
					<span v-if="item.meta" class="text-[13px] text-gray-700">{{ item.meta }}</span>
					<span v-if="item.note" class="line-clamp-2 whitespace-pre-line text-[13px] text-gray-700">
						“{{ item.note }}”
					</span>
					<AttachmentThumbnails v-if="item.attachments?.length" :files="item.attachments" class="mt-1" />
				</div>
			</div>
			<div class="flex flex-row gap-2 lg:ml-auto" @click.stop>
				<LeaveDecisionButtons v-if="item.leaveApplication" :leave-application="item.leaveApplication" class="w-full lg:w-auto" :full-width="!isDesktop" />
				<button
					v-else-if="item.action"
					type="button"
					class="min-h-[40px] w-full rounded-xl border border-line bg-white px-4 text-sm font-semibold text-ink hover:bg-gray-50 lg:w-auto"
					@click="item.open()"
				>
					{{ item.action }}
				</button>
			</div>
		</div>

		<div
			v-if="!items.length"
			class="rounded-xl border border-dashed border-[#D5DAD4] p-5 text-center text-sm text-gray-700"
		>
			{{ __("You are all caught up. New approvals and reminders will show up here.") }}
		</div>
	</section>
</template>

<script setup>
import { computed, inject } from "vue"
import { useRouter } from "vue-router"

import AttachmentThumbnails from "@/components/AttachmentThumbnails.vue"
import LeaveDecisionButtons from "@/components/LeaveDecisionButtons.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { homeData } from "@/data/home"
import { showExpenses } from "@/utils/navigation"
import { TONE_CLASSES, avatarColour, initials } from "@/utils/status"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const employee = inject("$employee")
const router = useRouter()
const isDesktop = useIsDesktop()

// phones show the first few on Home, with "See all" for the rest
const props = defineProps({ limit: { type: Number, default: 0 } })

const OTHER_ROUTES = {
	"Expense Claim": "ExpenseClaimsDashboard",
	"Shift Request": "AttendanceDashboard",
}

function dates(from, to) {
	const start = dayjs(from).format("ddd D MMM")
	return from === to ? start : `${start} – ${dayjs(to).format("ddd D MMM")}`
}

function openLeave(name) {
	return () => router.push({ name: "LeaveApplicationDetailView", params: { id: name } })
}

const items = computed(() => {
	const data = homeData.data
	if (!data) return []
	const list = []
	const myName = employee?.data?.employee_name || ""

	for (const row of data.leave_approvals || []) {
		list.push({
			key: `leave-${row.name}`,
			who: row.employee_name,
			initials: initials(row.employee_name),
			avatar: avatarColour(row.employee_name),
			kind: __("Leave request"),
			tone: "info",
			title: `${row.label} · ${dates(row.from_date, row.to_date)}`,
			meta: [
				row.total_leave_days == 1 ? __("1 day") : __("{0} days", [row.total_leave_days]),
				...(row.progress || []),
				row.document_missing && __("document due {0}", [dayjs(row.document_due_date).format("D MMM")]),
				row.end_date_after && __("end date moves to {0}", [dayjs(row.end_date_after).format("ddd D MMM YYYY")]),
			]
				.filter(Boolean)
				.join(" · "),
			note: row.description,
			attachments: row.attachments,
			leaveApplication: row.name,
			open: openLeave(row.name),
		})
	}

	for (const doc of data.missing_documents?.mine || []) {
		list.push({
			key: `my-doc-${doc.name}`,
			who: __("You"),
			initials: initials(myName) || "•",
			avatar: avatarColour(myName),
			kind: doc.overdue ? __("Document overdue") : __("Document needed"),
			tone: doc.overdue ? "bad" : "warn",
			title: __("{0} leave on {1}", [doc.label, dayjs(doc.from_date).format("ddd D MMM")]),
			meta: __("Upload by {0}", [dayjs(doc.document_due_date).format("D MMM")]),
			action: __("Upload"),
			open: openLeave(doc.name),
		})
	}

	for (const doc of data.missing_documents?.to_review || []) {
		list.push({
			key: `review-doc-${doc.name}`,
			who: doc.employee_name,
			initials: initials(doc.employee_name),
			avatar: avatarColour(doc.employee_name),
			kind: __("Document missing"),
			tone: "neutral",
			title: __("{0} leave on {1}", [doc.label, dayjs(doc.from_date).format("ddd D MMM")]),
			meta: __("Waiting for the upload"),
			action: __("View"),
			open: openLeave(doc.name),
		})
	}

	for (const row of data.other_approvals || []) {
		if (!row.count || (row.doctype === "Expense Claim" && !showExpenses.value)) continue
		list.push({
			key: `other-${row.doctype}`,
			who: row.label,
			initials: String(row.count),
			avatar: "#EEF0EE",
			kind: __("Waiting for you"),
			tone: "warn",
			title: row.count == 1 ? __("1 request to review") : __("{0} requests to review", [row.count]),
			action: __("Open"),
			open: () => router.push({ name: OTHER_ROUTES[row.doctype] }),
		})
	}
	return list
})

const shown = computed(() => (props.limit ? items.value.slice(0, props.limit) : items.value))
</script>
