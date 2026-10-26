<template>
	<!-- Today: what the employee needs to do now -->
	<section
		:aria-label="__('Today')"
		class="flex flex-col gap-4 rounded-2xl border border-line bg-white p-5 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between lg:gap-6 lg:p-7"
	>
		<div class="flex min-w-0 flex-1 flex-col gap-2.5 lg:basis-[300px]">
			<div class="flex flex-row items-center justify-between gap-2.5 lg:justify-start">
				<div class="flex flex-row items-center gap-2.5">
					<span class="text-xs font-bold uppercase tracking-[0.08em] text-gray-700">{{ __("Today") }}</span>
					<span :class="['rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[today.tone]]">
						{{ today.badge }}
					</span>
				</div>
				<span v-if="today.showClock" class="text-xl font-semibold tabular-nums text-ink lg:hidden">
					{{ clock }}
				</span>
			</div>
			<div class="flex flex-row items-center gap-3">
				<span
					v-if="today.done"
					class="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-[#E2F4EA] text-[#0F6B4C]"
				>
					<FeatherIcon name="check" class="h-5 w-5" />
				</span>
				<h2 class="text-[21px] font-bold tracking-tight text-ink lg:text-[26px]">{{ today.title }}</h2>
			</div>
			<p v-if="today.sub" class="text-sm leading-relaxed text-gray-700 lg:text-[15px]">{{ today.sub }}</p>
			<router-link
				v-if="lastLog?.time"
				:to="{ name: 'EmployeeCheckinListView' }"
				class="self-start text-sm font-medium text-brand-600 hover:text-brand-700"
			>
				{{ __("Check-in history") }}
			</router-link>
		</div>

		<div class="flex flex-col gap-3 lg:items-end">
			<div v-if="today.showClock" class="hidden text-[44px] font-semibold leading-none tracking-tight tabular-nums text-ink lg:block">
				{{ clock }}
			</div>
			<button
				v-if="canCheckIn && today.showButton"
				type="button"
				:class="[
					'flex min-h-[54px] items-center justify-center gap-2.5 rounded-xl px-7 text-base font-semibold text-white transition active:scale-[0.98] lg:min-h-[52px]',
					today.tone === 'warn' ? 'bg-[#B86200] hover:bg-[#9A5200]' : 'bg-brand-600 hover:bg-brand-700',
				]"
				:disabled="checkins.list.loading"
				@click="openCheckin"
			>
				<FeatherIcon name="camera" class="h-5 w-5" />
				{{ today.buttonLabel }}
			</button>
			<button
				v-else-if="canCheckIn && today.offerAnyway"
				type="button"
				class="self-start rounded-lg px-1 py-2 text-sm font-semibold text-brand-600 hover:text-brand-700 lg:self-end"
				@click="openCheckin"
			>
				{{ __("Working today? Check in") }}
			</button>
		</div>
	</section>

	<ion-modal
		v-if="canCheckIn"
		:is-open="sheetOpen"
		:class="isDesktop ? 'centered-dialog' : ''"
		:initial-breakpoint="isDesktop ? undefined : 1"
		:breakpoints="isDesktop ? undefined : [0, 1]"
		@didDismiss="sheetOpen = false"
	>
		<div class="flex max-h-[90vh] w-full flex-col gap-4 overflow-y-auto p-5">
			<div class="flex flex-row items-center justify-between">
				<h2 class="text-xl font-bold text-ink">
					{{ __("Check in") }} · <span class="tabular-nums">{{ dayjs(checkinTimestamp).format("HH:mm") }}</span>
				</h2>
				<button
					type="button"
					class="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-ink"
					:aria-label="__('Close')"
					@click="sheetOpen = false"
				>
					<FeatherIcon name="x" class="h-5 w-5" />
				</button>
			</div>

			<template v-if="settings.data?.allow_geolocation_tracking">
				<div
					v-if="locationProblem"
					class="w-full rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800"
					role="alert"
				>
					<div class="font-semibold">{{ locationProblem.title }}</div>
					<div class="mt-1">{{ locationProblem.help }}</div>
					<Button class="mt-3 w-full" variant="subtle" @click="fetchLocation">
						<template #prefix><FeatherIcon name="map-pin" class="w-4" /></template>
						{{ __("Try again") }}
					</Button>
				</div>
				<div v-else class="flex flex-row items-center justify-between text-sm">
					<span class="text-gray-700">{{ today.shift || __("Location") }}</span>
					<span :class="['font-semibold', locationFound ? 'text-[#0F6B4C]' : 'text-gray-700']">
						{{ locationFound ? __("Location found") : locationStatus || __("Finding your location…") }}
					</span>
				</div>
			</template>

			<!-- an office shift checked in from too far away: allowed with a reason, shown to supervisors and HR -->
			<div
				v-if="outsideOffice"
				class="flex flex-col gap-3 rounded-xl border border-[#F2C77C] bg-[#FDEFD6] p-3.5 text-[#8A4B00]"
				role="alert"
			>
				<div>
					<div class="text-[15px] font-semibold">
						{{ __("You are {0} from {1}", [distanceLabel(distance), officeLocation.data.name]) }}
					</div>
					<div class="mt-1 text-sm leading-snug">
						{{ __("Office check-in counts within {0} m. Why are you checking in from here? Your supervisors and HR will see this today.", [officeLocation.data.radius]) }}
					</div>
				</div>
				<div role="radiogroup" :aria-label="__('Reason')" class="flex flex-col gap-2">
					<button
						v-for="option in officeLocation.data.reasons"
						:key="option"
						type="button"
						role="radio"
						:aria-checked="outsideReason === option"
						:class="[
							'flex min-h-[48px] items-center gap-3 rounded-xl border-2 bg-white px-3.5 text-left text-[15px] font-semibold text-ink',
							outsideReason === option ? 'border-[#B86200]' : 'border-transparent',
						]"
						@click="outsideReason = option"
					>
						<span
							:class="[
								'flex h-5 w-5 flex-none items-center justify-center rounded-full border-2',
								outsideReason === option ? 'border-[#B86200]' : 'border-[#B9C0BA]',
							]"
						>
							<span v-if="outsideReason === option" class="h-2.5 w-2.5 rounded-full bg-[#B86200]"></span>
						</span>
						{{ option }}
					</button>
				</div>
			</div>

			<SelfieCamera v-if="selfieRequired" v-model="selfie" />

			<div
				v-if="today.tone === 'warn'"
				class="rounded-xl bg-[#FDEFD6] px-3 py-2.5 text-sm text-[#8A4B00]"
			>
				{{ __("This check-in counts as late.") }}
			</div>

			<button
				type="button"
				class="flex min-h-[54px] w-full items-center justify-center rounded-xl bg-brand-600 text-base font-semibold text-white hover:bg-brand-700 disabled:bg-gray-300 disabled:text-gray-600"
				:disabled="
					(selfieRequired && !selfie) ||
					(locationRequired && !locationFound) ||
					(outsideOffice && !outsideReason) ||
					submitting
				"
				@click="submitLog('IN')"
			>
				{{ submitting ? __("Checking in…") : selfieRequired ? __("Check in with this photo") : __("Confirm check-in") }}
			</button>
		</div>
	</ion-modal>
</template>

<script setup>
import { createListResource, createResource, toast, FeatherIcon } from "frappe-ui"
import { computed, inject, ref, onMounted, onBeforeUnmount } from "vue"
import { IonModal } from "@ionic/vue"

import { settings } from "@/data/settings"
import { homeData } from "@/data/home"
import SelfieCamera from "@/components/SelfieCamera.vue"
import { useIsDesktop } from "@/composables/useIsDesktop"
import { TONE_CLASSES } from "@/utils/status"
import { getBlockedHelp, getLocationOffHelp, watchPermission } from "@/utils/permissionHelp"

const DOCTYPE = "Employee Checkin"

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")
const isDesktop = useIsDesktop()

const sheetOpen = ref(false)
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")
const selfie = ref("")
const selfieRequired = computed(() => Boolean(settings.data?.require_selfie_for_checkin))
const canCheckIn = computed(() => Boolean(settings.data?.allow_employee_checkin_from_mobile_app))

// the office of today's shift, if it has a check-in radius
const officeLocation = createResource({ url: "hrms.api.employee_app.get_my_checkin_location" })
const outsideReason = ref("")

// metres between two points on the globe (haversine), as the server measures it
function metresBetween(lat1, lon1, lat2, lon2) {
	const rad = (deg) => (deg * Math.PI) / 180
	const a =
		Math.sin(rad(lat2 - lat1) / 2) ** 2 +
		Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
	return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}
const distance = computed(() => {
	const office = officeLocation.data
	if (!office || !locationFound.value) return null
	return metresBetween(office.latitude, office.longitude, latitude.value, longitude.value)
})
const outsideOffice = computed(() => distance.value != null && distance.value > officeLocation.data.radius)
const distanceLabel = (metres) =>
	metres >= 1000 ? __("{0} km", [(metres / 1000).toFixed(1)]) : __("{0} m", [Math.round(metres)])

// with a live selfie required, the server takes the photo, sets the time and creates the check-in
const selfieCheckin = createResource({
	url: "hrms.hr.doctype.employee_checkin.employee_checkin.add_log_with_selfie",
})

const checkins = createListResource({
	doctype: DOCTYPE,
	fields: ["name", "employee", "employee_name", "log_type", "time", "device_id"],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
	pageLength: 5,
})
checkins.reload()

const lastLog = computed(() => checkins.data?.[0] || null)
const submitting = computed(() => checkins.insert.loading || selfieCheckin.loading)

// a clock for the card, refreshed every half minute
const now = ref(dayjs())
let clockTimer = null
const clock = computed(() => now.value.format("HH:mm"))

// check-in only (HR: no check-out); the card follows the employee's status today from the server
const me = computed(() => homeData.data?.me || null)
const firstInToday = computed(() => {
	if (me.value?.checked_in_at) return dayjs(me.value.checked_in_at)
	const log = (checkins.data || []).find(
		(row) => row.log_type !== "OUT" && dayjs(row.time).isSame(now.value, "day")
	)
	return log ? dayjs(log.time) : null
})

const today = computed(() => {
	const row = me.value || {}
	const shift = row.shift || ""
	const lateAfter = row.late_after ? dayjs(row.late_after) : null
	const base = { shift, showClock: false, showButton: false, offerAnyway: false, done: false, sub: "" }

	if (row.status === "On leave") {
		return {
			...base,
			badge: __("On leave"),
			tone: "info",
			title: __("You are on leave today"),
			sub: row.leave_to_date
				? __("{0} · until {1}", [row.leave_label || __("Leave"), dayjs(row.leave_to_date).format("ddd D MMM")])
				: row.leave_label,
		}
	}
	if (firstInToday.value) {
		const late = row.status === "Late"
		const outside = row.outside_office
		return {
			...base,
			badge: late ? __("Late") : __("On time"),
			tone: late ? "warn" : "ok",
			done: true,
			title: __("Checked in at {0}", [firstInToday.value.format("HH:mm")]),
			sub: outside
				? [__("Outside the office ({0})", [distanceLabel(outside.office_distance)]), outside.outside_office_reason].join(" · ")
				: [shift && __("{0} today", [shift]), __("nothing else to do")].filter(Boolean).join(" · "),
		}
	}
	if (row.status === "Holiday") {
		return {
			...base,
			badge: __("Holiday"),
			tone: "neutral",
			title: row.holiday || __("Day off"),
			sub: __("No check-in needed today."),
			offerAnyway: true,
		}
	}
	if (lateAfter && now.value.isAfter(lateAfter)) {
		return {
			...base,
			badge: __("Late"),
			tone: "warn",
			title: __("You can still check in"),
			sub: __("After {0} counts as late.", [lateAfter.format("HH:mm")]),
			showClock: true,
			showButton: true,
			buttonLabel: __("Check in late"),
		}
	}
	return {
		...base,
		badge: __("Open"),
		tone: "ok",
		title: __("Check-in is open"),
		sub: !shift
			? __("No schedule set for today.")
			: lateAfter
				? __("{0} today · on time until {1}", [shift, lateAfter.format("HH:mm")])
				: __("{0} today", [shift]),
		showClock: true,
		showButton: true,
		buttonLabel: __("Check in"),
	}
})

// with geolocation tracking on, the server refuses a check-in without a location
const locationRequired = computed(() => Boolean(settings.data?.allow_geolocation_tracking))
const locationFound = ref(false)
const locationProblem = ref(null)

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude
	locationFound.value = true
	locationProblem.value = null
	locationStatus.value = ""
}

function handleLocationError(error) {
	locationStatus.value = ""
	if (error?.code === error?.PERMISSION_DENIED) {
		locationProblem.value = {
			title: __("Location is blocked for this site"),
			help: getBlockedHelp(__, "location"),
		}
	} else if (error?.code === error?.POSITION_UNAVAILABLE) {
		locationProblem.value = {
			title: __("Your location could not be found"),
			help: getLocationOffHelp(__),
		}
	} else {
		locationProblem.value = {
			title: __("Finding your location took too long"),
			help: __("Move closer to a window or turn on Wi-Fi, then tap Try again."),
		}
	}
}

// asks the browser for the location; if it hasn't been decided yet, the browser shows its own "Allow?" pop-up
const fetchLocation = () => {
	locationFound.value = false
	locationProblem.value = null
	if (!navigator.geolocation) {
		locationProblem.value = {
			title: __("This browser can't share its location"),
			help: __("Open this page in Chrome, Edge or Safari to check in."),
		}
		return
	}
	locationStatus.value = __("Finding your location…")
	navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError, {
		enableHighAccuracy: true,
		timeout: 20000,
		maximumAge: 0,
	})
}

// allowed in the browser's site settings while the sheet is open: pick the location up without a reload
watchPermission("geolocation", (state) => {
	if (state === "granted" && locationRequired.value && !locationFound.value) fetchLocation()
})

function openCheckin() {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")
	selfie.value = ""
	outsideReason.value = ""
	sheetOpen.value = true
	if (settings.data?.allow_geolocation_tracking) {
		officeLocation.reload()
		fetchLocation()
	}
}

function onCheckedIn() {
	sheetOpen.value = false
	checkins.reload()
	homeData.reload()
	toast({
		title: __("Checked in"),
		text: __("Have a good day!"),
		icon: "check-circle",
		position: "bottom-center",
		iconClasses: "text-green-500",
	})
}

function showErrors(error) {
	for (const message of error?.messages?.length ? error.messages : [__("Check-in failed!")]) {
		toast({
			title: __("Error"),
			text: message,
			icon: "alert-circle",
			position: "bottom-center",
			iconClasses: "text-red-500",
		})
	}
}

const submitLog = (logType) => {
	if (selfieRequired.value) {
		selfieCheckin.submit(
			{
				log_type: logType,
				selfie: selfie.value,
				latitude: latitude.value || null,
				longitude: longitude.value || null,
				outside_office_reason: outsideOffice.value ? outsideReason.value : null,
			},
			{ onSuccess: onCheckedIn, onError: showErrors }
		)
		return
	}

	checkins.insert.submit(
		{
			employee: employee.data.name,
			log_type: logType,
			time: checkinTimestamp.value,
			latitude: latitude.value,
			longitude: longitude.value,
			outside_office_reason: outsideOffice.value ? outsideReason.value : null,
		},
		{
			onSuccess(data) {
				if (!data?.name) return showErrors()
				onCheckedIn()
			},
			onError: showErrors,
		}
	)
}

onMounted(() => {
	clockTimer = setInterval(() => (now.value = dayjs()), 30000)
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype == DOCTYPE) {
			checkins.reload()
		}
	})
})

onBeforeUnmount(() => {
	clearInterval(clockTimer)
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})
</script>
