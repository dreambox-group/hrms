<template>
	<div :class="['flex flex-row gap-2', fullWidth ? 'w-full' : 'justify-end']">
		<button
			type="button"
			:class="[
				'flex min-h-[40px] items-center justify-center gap-1.5 rounded-xl border border-line bg-white px-4 text-sm font-semibold text-[#A8231A] hover:bg-red-50 disabled:opacity-60',
				fullWidth ? 'min-h-[44px] flex-1' : '',
			]"
			:disabled="resource.loading"
			@click.stop="decide('Rejected')"
		>
			<FeatherIcon name="x" class="h-4 w-4" />
			{{ __("Reject") }}
		</button>
		<button
			type="button"
			:class="[
				'flex min-h-[40px] items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-[18px] text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60',
				fullWidth ? 'min-h-[44px] flex-1' : '',
			]"
			:disabled="resource.loading"
			@click.stop="decide('Approved')"
		>
			<FeatherIcon name="check" class="h-4 w-4" />
			{{ __("Approve") }}
		</button>
	</div>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon, toast } from "frappe-ui"

import { cutiPenggantiDecision, homeData, leaveDecision } from "@/data/home"
import { myLeaves, teamLeaves } from "@/data/leaves"

const __ = inject("$translate")
// a leave request, or a Cuti Pengganti request (a day worked, for a day off)
const props = defineProps({
	leaveApplication: { type: String, default: "" },
	cutiPengganti: { type: String, default: "" },
	fullWidth: { type: Boolean, default: false },
})
const emit = defineEmits(["decided"])
const resource = computed(() => (props.cutiPengganti ? cutiPenggantiDecision : leaveDecision))

function decide(decision) {
	resource.value.submit(
		props.cutiPengganti
			? { name: props.cutiPengganti, decision }
			: { leave_application: props.leaveApplication, decision },
		{
			onSuccess(status) {
				toast({
					title: __("Done"),
					text:
						status === "Open"
							? __("Your decision was saved. The request is still waiting for other approvers.")
							: props.cutiPengganti
								? __("The Cuti Pengganti request is now {0}.", [__(status)])
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
