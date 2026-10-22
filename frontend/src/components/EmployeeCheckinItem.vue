<template>
	<ListItem>
		<template #left>
			<FeatherIcon :name="props.doc.log_type === 'OUT' ? 'log-out' : 'log-in'" class="h-5 w-5 text-gray-600" />
			<div class="flex flex-col items-start gap-1">
				<div class="text-base font-medium text-ink">{{ label }}</div>
				<div class="text-xs font-normal text-gray-700">
					{{ dayjs(props.doc.time).format("ddd D MMM YYYY · HH:mm") }}
				</div>
			</div>
		</template>
		<template #right>
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed, inject } from "vue"
import { FeatherIcon } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"

const __ = inject("$translate")
const dayjs = inject("$dayjs")

const props = defineProps({
	doc: {
		type: Object,
	},
})

// plain words instead of "Log Type: IN"; an entry without a type is still a check-in
const label = computed(() => (props.doc.log_type === "OUT" ? __("Checked out") : __("Checked in")))
</script>
