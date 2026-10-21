<template>
	<div :class="['flex flex-row gap-2', fullWidth ? 'w-full' : 'justify-end']">
		<Button
			variant="subtle"
			theme="red"
			:class="fullWidth ? 'flex-1 py-5' : ''"
			:loading="leaveDecision.loading"
			@click.stop="decide('Rejected')"
		>
			<template #prefix><FeatherIcon name="x" class="w-4" /></template>
			{{ __("Reject") }}
		</Button>
		<Button
			variant="solid"
			:class="fullWidth ? 'flex-1 py-5' : ''"
			:loading="leaveDecision.loading"
			@click.stop="decide('Approved')"
		>
			<template #prefix><FeatherIcon name="check" class="w-4" /></template>
			{{ __("Approve") }}
		</Button>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon, toast } from "frappe-ui"

import { homeData, leaveDecision } from "@/data/home"
import { myLeaves, teamLeaves } from "@/data/leaves"

const __ = inject("$translate")
const props = defineProps({
	leaveApplication: { type: String, required: true },
	fullWidth: { type: Boolean, default: false },
})
const emit = defineEmits(["decided"])

function decide(decision) {
	leaveDecision.submit(
		{ leave_application: props.leaveApplication, decision },
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
				myLeaves.reload()
				emit("decided", status)
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
</script>
