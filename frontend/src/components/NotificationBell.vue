<template>
	<div class="relative">
		<button
			type="button"
			class="relative flex h-11 w-11 items-center justify-center rounded-xl text-ink hover:bg-gray-100"
			:aria-label="unread ? __('Notifications, {0} unread', [unread]) : __('Notifications')"
			:aria-expanded="open"
			@click="toggle"
		>
			<FeatherIcon name="bell" class="h-5 w-5" />
			<span
				v-if="unread"
				class="absolute -top-0.5 -right-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[#C4321F] px-1 text-[11px] font-bold text-white"
			>
				{{ unread > 99 ? "99+" : unread }}
			</span>
		</button>

		<!-- wide screens: a drop-down; phones go to the Notifications page -->
		<template v-if="open">
			<div class="fixed inset-0 z-40" @click="open = false"></div>
			<div
				class="absolute right-0 top-12 z-50 w-[360px] overflow-hidden rounded-2xl border border-line bg-white shadow-xl"
			>
				<div class="flex items-center justify-between border-b border-line px-4 py-3">
					<span class="text-[15px] font-semibold text-ink">{{ __("Notifications") }}</span>
					<button
						v-if="unread"
						type="button"
						class="rounded-lg px-2 py-1.5 text-sm font-semibold text-brand-600 hover:bg-brand-50"
						@click="markAllNotificationsAsRead.submit()"
					>
						{{ __("Mark all as read") }}
					</button>
				</div>
				<div class="max-h-[420px] overflow-y-auto">
					<button
						v-for="item in latest"
						:key="item.name"
						type="button"
						:class="[
							'flex w-full gap-3 border-b border-[#F1F3F0] px-4 py-3 text-left hover:bg-gray-50',
							item.read ? 'bg-white' : 'bg-brand-50',
						]"
						@click="openItem(item)"
					>
						<span
							:class="['mt-1.5 h-2 w-2 flex-none rounded-full', item.read ? 'bg-gray-300' : 'bg-brand-600']"
						></span>
						<span class="flex flex-col gap-0.5">
							<span class="text-sm text-ink" v-html="item.message"></span>
							<span class="text-xs text-gray-600">{{ dayjs(item.creation).fromNow() }}</span>
						</span>
					</button>
					<div v-if="!latest.length" class="px-4 py-8 text-center text-sm text-gray-600">
						{{ __("You have no notifications") }}
					</div>
				</div>
				<router-link
					:to="{ name: 'Notifications' }"
					class="block px-4 py-3 text-center text-sm font-semibold text-brand-600 hover:bg-gray-50"
					@click="open = false"
				>
					{{ __("See all") }}
				</router-link>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"
import { useRouter } from "vue-router"
import { FeatherIcon } from "frappe-ui"

import { useIsDesktop } from "@/composables/useIsDesktop"
import {
	markAllNotificationsAsRead,
	markNotificationAsRead,
	notificationRoute,
	notifications,
	unreadNotificationsCount,
} from "@/data/notifications"

const __ = inject("$translate")
const dayjs = inject("$dayjs")
const router = useRouter()
const isDesktop = useIsDesktop()

const open = ref(false)
const unread = computed(() => unreadNotificationsCount.data || 0)
const latest = computed(() => (notifications.data || []).slice(0, 6))

function toggle() {
	if (!isDesktop.value) {
		router.push({ name: "Notifications" })
		return
	}
	open.value = !open.value
	if (open.value) notifications.submit({ start: 0, limit: 20 })
}

function openItem(item) {
	if (!item.read) {
		item.read = 1
		markNotificationAsRead.submit({ name: item.name })
	}
	open.value = false
	const route = notificationRoute(item)
	if (route) router.push(route)
}
</script>
