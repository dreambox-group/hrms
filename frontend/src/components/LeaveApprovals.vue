<template>
	<div v-if="!rows.length" class="text-sm text-gray-500 py-3">
		{{ __("Nothing is waiting for your approval.") }}
	</div>

	<!-- wide screens: a table -->
	<div v-else-if="layout === 'table'" class="overflow-x-auto">
		<table class="w-full min-w-[640px] text-sm">
			<thead>
				<tr class="text-left text-gray-500">
					<th scope="col" class="py-2 pr-3 font-medium">{{ __("Employee") }}</th>
					<th scope="col" class="py-2 px-3 font-medium">{{ __("Leave") }}</th>
					<th scope="col" class="py-2 px-3 font-medium">{{ __("Dates") }}</th>
					<th scope="col" class="py-2 px-3 font-medium">{{ __("Approvals so far") }}</th>
					<th scope="col" class="py-2 pl-3 font-medium text-right">{{ __("Your decision") }}</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="row in rows" :key="row.name" class="border-t align-middle">
					<td class="py-3 pr-3">
						<div class="font-semibold text-gray-900">{{ row.employee_name }}</div>
						<div class="text-gray-500 text-xs">{{ row.department }}</div>
					</td>
					<td class="py-3 px-3">{{ row.label }}</td>
					<td class="py-3 px-3 whitespace-nowrap">
						{{ dates(row) }} · {{ __("{0} days", [row.total_leave_days]) }}
					</td>
					<td class="py-3 px-3 text-gray-500 text-xs">
						<div v-for="line in row.progress" :key="line">{{ line }}</div>
					</td>
					<td class="py-3 pl-3 text-right whitespace-nowrap">
						<LeaveDecisionButtons :row="row" />
					</td>
				</tr>
			</tbody>
		</table>
	</div>

	<!-- phones: cards -->
	<div v-else class="flex flex-col gap-3">
		<div v-for="row in rows" :key="row.name" class="rounded-lg border bg-white p-4 flex flex-col gap-1.5">
			<div class="flex justify-between gap-3">
				<span class="font-semibold text-gray-900">{{ row.employee_name }}</span>
				<span class="text-sm text-gray-500">{{ row.label }}</span>
			</div>
			<div class="text-sm">{{ dates(row) }} · {{ __("{0} days", [row.total_leave_days]) }}</div>
			<div class="text-xs text-gray-500">{{ row.progress.join(" · ") }}</div>
			<div class="mt-2">
				<LeaveDecisionButtons :row="row" full-width />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, defineComponent, h, inject } from "vue"
import { useRouter } from "vue-router"
import { Button, toast } from "frappe-ui"

import { homeData, leaveDecision } from "@/data/home"
import { teamLeaves } from "@/data/leaves"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()

defineProps({ layout: { type: String, default: "table" } })

const rows = computed(() => homeData.data?.leave_approvals || [])
const byLevels = computed(() => Boolean(homeData.data?.approval_by_levels))

function dates(row) {
	const from = dayjs(row.from_date).format("D MMM")
	return row.from_date === row.to_date ? from : `${from} – ${dayjs(row.to_date).format("D MMM")}`
}

function decide(row, decision) {
	leaveDecision.submit(
		{ leave_application: row.name, decision },
		{
			onSuccess(status) {
				toast({
					title: __("Done"),
					text:
						status === "Open"
							? __("Your decision was saved. The request is still waiting for other approvers.")
							: __("The leave request is now {0}.", [__(status)]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
				homeData.reload()
				teamLeaves.reload()
			},
			onError(error) {
				toast({
					title: __("Error"),
					text: error.messages?.[0] || __("Your decision could not be saved."),
					icon: "alert-circle",
					position: "bottom-center",
					iconClasses: "text-red-500",
				})
			},
		}
	)
}

function open(row) {
	router.push({ name: "LeaveApplicationDetailView", params: { id: row.name } })
}

// Approve / Reject with approval by levels; otherwise the stock flow on the request's own page
const LeaveDecisionButtons = defineComponent({
	props: { row: Object, fullWidth: Boolean },
	setup(props) {
		return () => {
			const width = props.fullWidth ? "flex-1 py-5" : ""
			if (!byLevels.value) {
				return h(Button, { variant: "subtle", class: width, onClick: () => open(props.row) }, () => __("Open"))
			}
			return h("div", { class: ["flex gap-2", props.fullWidth ? "w-full" : "justify-end"] }, [
				h(
					Button,
					{
						variant: "subtle",
						theme: "red",
						class: width,
						loading: leaveDecision.loading,
						onClick: () => decide(props.row, "Rejected"),
					},
					() => __("Reject")
				),
				h(
					Button,
					{
						variant: "solid",
						class: width,
						loading: leaveDecision.loading,
						onClick: () => decide(props.row, "Approved"),
					},
					() => __("Approve")
				),
			])
		}
	},
})
</script>
