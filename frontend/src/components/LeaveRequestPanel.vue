<template>
	<ion-modal class="side-panel" :is-open="leaveRequestOpen" @didDismiss="leaveRequestOpen = false">
		<div class="flex h-full flex-col bg-white">
			<div class="flex flex-row items-center justify-between border-b border-[#EEF0EE] px-6 py-4">
				<h1 class="text-xl font-bold text-ink">{{ __("Request leave") }}</h1>
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-ink"
					:aria-label="__('Close')"
					@click="leaveRequestOpen = false"
				>
					<FeatherIcon name="x" class="h-5 w-5" />
				</button>
			</div>
			<LeaveRequestForm class="min-h-0 flex-1" @close="leaveRequestOpen = false" />
		</div>
	</ion-modal>
</template>

<script setup>
import { inject } from "vue"
import { IonModal } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"

import LeaveRequestForm from "@/components/LeaveRequestForm.vue"
import { leaveRequestOpen } from "@/composables/leaveRequest"

const __ = inject("$translate")
</script>
