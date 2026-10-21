<template>
	<div class="flex flex-col gap-2">
		<label
			class="flex flex-row items-center justify-center gap-2 rounded border border-dashed px-3 py-3 text-sm font-medium text-gray-800 cursor-pointer"
		>
			<FeatherIcon name="upload" class="h-4 w-4" />
			{{ leaveDocumentUpload.loading ? __("Uploading…") : __("Upload the supporting document") }}
			<input
				type="file"
				class="hidden"
				accept="image/*,application/pdf"
				:disabled="leaveDocumentUpload.loading"
				@change="upload"
			/>
		</label>
		<div class="text-xs text-gray-500">{{ __("A photo or PDF, up to 10 MB.") }}</div>
	</div>
</template>

<script setup>
import { inject } from "vue"
import { FeatherIcon, toast } from "frappe-ui"

import { homeData, leaveDocumentUpload } from "@/data/home"

const __ = inject("$translate")
const props = defineProps({ leaveApplication: { type: String, required: true } })
const emit = defineEmits(["uploaded"])

function upload(event) {
	const file = event.target.files?.[0]
	event.target.value = ""
	if (!file) return

	const reader = new FileReader()
	reader.onload = () => {
		leaveDocumentUpload.submit(
			{ leave_application: props.leaveApplication, filename: file.name, content: reader.result },
			{
				onSuccess(uploaded) {
					toast({
						title: __("Uploaded"),
						text: __("The document was added to your leave request."),
						icon: "check-circle",
						position: "bottom-center",
						iconClasses: "text-green-500",
					})
					homeData.reload()
					emit("uploaded", uploaded)
				},
				onError(error) {
					toast({
						title: __("Error"),
						text: error.messages?.[0] || __("The document could not be uploaded."),
						icon: "alert-circle",
						position: "bottom-center",
						iconClasses: "text-red-500",
					})
				},
			}
		)
	}
	reader.readAsDataURL(file)
}
</script>
