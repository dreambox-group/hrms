<template>
	<BaseLayout
		:pageTitle="props.id ? __('Leave request') : __('Request leave')"
		:backTo="{ name: 'LeavesDashboard' }"
		:backLabel="__('Leaves')"
	>
		<template #body>
			<div class="w-full px-4 pb-24 pt-4 lg:px-6 lg:pt-6">
				<div class="mx-auto w-full max-w-[560px] overflow-hidden rounded-2xl border border-line bg-white">
					<LeaveDetail v-if="props.id" :name="props.id" class="p-5 lg:p-6" />
					<LeaveRequestForm v-else @close="router.back()" />
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { inject } from "vue"
import { useRouter } from "vue-router"

import BaseLayout from "@/components/BaseLayout.vue"
import LeaveDetail from "@/components/LeaveDetail.vue"
import LeaveRequestForm from "@/components/LeaveRequestForm.vue"

const __ = inject("$translate")
const router = useRouter()

// a new request, or one request (from a notification, the To-do or the Leaves page)
const props = defineProps({
	id: {
		type: String,
		required: false,
	},
})
</script>
