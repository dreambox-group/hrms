<template>
	<div>
		<div class="flex h-2 overflow-hidden rounded-full bg-[#EEF0EE]">
			<span class="bg-ink" :style="{ width: pct(row.used) }"></span>
			<span class="bg-[#B86200]" :style="{ width: pct(row.pending) }"></span>
			<span class="bg-brand-600" :style="{ width: pct(row.left) }"></span>
		</div>
		<div class="mt-2 flex flex-row flex-wrap gap-x-4 gap-y-1 text-[13px] text-gray-700">
			<span class="flex flex-row items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-ink"></span>{{ __("{0} used", [row.used]) }}</span>
			<span class="flex flex-row items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-[#B86200]"></span>{{ __("{0} waiting", [row.pending]) }}</span>
			<span class="flex flex-row items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-brand-600"></span>{{ __("{0} left", [row.left]) }}</span>
		</div>
	</div>
</template>

<script setup>
import { inject } from "vue"

const __ = inject("$translate")
const props = defineProps({ row: { type: Object, required: true } })

// used / waiting for approval / left, as parts of the allocation
function pct(value) {
	const total = props.row.used + props.row.pending + props.row.left || props.row.total || 1
	return `${Math.max(0, (value / total) * 100)}%`
}
</script>
