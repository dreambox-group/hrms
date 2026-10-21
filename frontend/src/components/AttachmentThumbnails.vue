<template>
	<div v-if="files.length" class="flex flex-row flex-wrap gap-2">
		<button
			v-for="file in files"
			:key="file.name"
			type="button"
			class="h-14 w-14 overflow-hidden rounded border bg-gray-50 flex items-center justify-center"
			:aria-label="__('Open {0}', [file.file_name])"
			@click.stop="open(file)"
		>
			<img v-if="isImage(file)" :src="file.file_url" :alt="file.file_name" class="h-full w-full object-cover" />
			<span v-else class="flex flex-col items-center gap-0.5 text-[10px] text-gray-600 px-1">
				<FeatherIcon name="file-text" class="h-5 w-5" />
				<span class="truncate max-w-[3rem]">{{ extension(file) }}</span>
			</span>
		</button>

		<ion-modal class="attachment-preview" :is-open="Boolean(selected)" @didDismiss="selected = null">
			<FilePreviewModal v-if="selected" :file="selected" />
		</ion-modal>
	</div>
</template>

<script setup>
import { inject, ref } from "vue"
import { IonModal } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"

import FilePreviewModal from "@/components/FilePreviewModal.vue"

const __ = inject("$translate")
defineProps({ files: { type: Array, default: () => [] } })

const selected = ref(null)
const IMAGE = /\.(jpe?g|png|gif|webp|heic)$/i

function isImage(file) {
	return IMAGE.test(file.file_name || file.file_url || "")
}

function extension(file) {
	return (file.file_name || "").split(".").pop().toUpperCase()
}

function open(file) {
	selected.value = file
}
</script>

<style>
/* the preview opens as a large sheet, not the modal's default (content-sized) height */
ion-modal.attachment-preview {
	--height: 85vh;
	--width: min(900px, 96vw);
}
</style>
