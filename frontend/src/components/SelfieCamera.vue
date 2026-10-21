<template>
	<div class="flex flex-col items-center gap-3 w-full">
		<div
			v-if="problem"
			class="w-full rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"
			role="alert"
		>
			<div class="font-semibold">{{ problem.title }}</div>
			<div class="mt-1">{{ problem.help }}</div>
		</div>

		<div class="relative w-full overflow-hidden rounded-lg bg-gray-900 aspect-[4/3]">
			<video
				v-show="streaming"
				ref="video"
				class="h-full w-full object-cover -scale-x-100"
				autoplay
				playsinline
				muted
			></video>
			<img
				v-if="photo"
				:src="photo"
				:alt="__('Your selfie')"
				class="h-full w-full object-cover -scale-x-100"
			/>
			<div
				v-if="!streaming && !photo"
				class="absolute inset-0 flex items-center justify-center text-sm text-gray-300 p-4 text-center"
			>
				{{ starting ? __("Opening the camera…") : __("The camera is off") }}
			</div>
		</div>

		<Button v-if="streaming" variant="solid" class="w-full py-5" @click="snap">
			<template #prefix><FeatherIcon name="camera" class="w-4" /></template>
			{{ __("Take selfie") }}
		</Button>
		<Button v-else-if="photo" variant="subtle" class="w-full py-5" @click="start">
			<template #prefix><FeatherIcon name="refresh-cw" class="w-4" /></template>
			{{ __("Retake selfie") }}
		</Button>
		<Button v-else-if="!starting" variant="subtle" class="w-full py-5" @click="start">
			<template #prefix><FeatherIcon name="camera" class="w-4" /></template>
			{{ problem ? __("Try again") : __("Open camera") }}
		</Button>
	</div>
</template>

<script setup>
import { inject, onBeforeUnmount, onMounted, ref } from "vue"
import { FeatherIcon } from "frappe-ui"

import { getBlockedHelp, watchPermission } from "@/utils/permissionHelp"

const __ = inject("$translate")
const emit = defineEmits(["update:modelValue"])
defineProps({ modelValue: { type: String, default: "" } })

// the photo sent to the server: at most this many pixels on its long side
const MAX_SIDE = 1024

const video = ref(null)
const photo = ref("")
const streaming = ref(false)
const starting = ref(false)
const problem = ref(null)
let stream = null

function fail(error) {
	if (!window.isSecureContext) {
		problem.value = {
			title: __("The camera needs a secure connection"),
			help: __("Open this page on its https:// address."),
		}
	} else if (error && ["NotAllowedError", "SecurityError"].includes(error.name)) {
		problem.value = { title: __("The camera is blocked for this site"), help: getBlockedHelp(__, "camera") }
	} else if (!error || ["NotFoundError", "OverconstrainedError"].includes(error.name)) {
		problem.value = {
			title: __("No camera was found"),
			help: __("Use a phone, or a computer with a webcam."),
		}
	} else if (error.name === "NotReadableError") {
		problem.value = {
			title: __("The camera is in use"),
			help: __("Close the other app using it (for example a video call), then tap Open camera."),
		}
	} else {
		problem.value = { title: __("Could not open the camera"), help: __("Please try again.") }
	}
}

async function start() {
	problem.value = null
	photo.value = ""
	emit("update:modelValue", "")
	if (!navigator.mediaDevices?.getUserMedia) return fail()

	starting.value = true
	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } },
			audio: false,
		})
	} catch (error) {
		starting.value = false
		return fail(error)
	}
	starting.value = false
	streaming.value = true
	video.value.srcObject = stream
}

function stop() {
	stream?.getTracks().forEach((track) => track.stop())
	stream = null
	streaming.value = false
}

function snap() {
	const el = video.value
	if (!el?.videoWidth) return
	const scale = Math.min(1, MAX_SIDE / Math.max(el.videoWidth, el.videoHeight))
	const canvas = document.createElement("canvas")
	canvas.width = Math.round(el.videoWidth * scale)
	canvas.height = Math.round(el.videoHeight * scale)
	canvas.getContext("2d").drawImage(el, 0, 0, canvas.width, canvas.height)
	photo.value = canvas.toDataURL("image/jpeg", 0.85)
	stop()
	emit("update:modelValue", photo.value)
}

onMounted(() => {
	// allowed in the browser's site settings while this is open: open the camera without a reload
	watchPermission("camera", (state) => {
		if (state === "granted" && !streaming.value && !photo.value) start()
	})
	start()
})
onBeforeUnmount(stop)
</script>
