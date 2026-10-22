<template>
	<BaseLayout :pageTitle="__('Notifications')" :backTo="{ name: 'Home' }" :backLabel="__('Home')">
		<template #actions>
			<div class="flex flex-row gap-2">
				<Button v-if="allowPushNotifications" variant="outline" @click="router.push({ name: 'Settings' })">
					<template #prefix><FeatherIcon name="settings" class="w-4" /></template>
					{{ __("Settings") }}
				</Button>
				<Button
					v-if="unreadNotificationsCount.data"
					variant="outline"
					:loading="markAllNotificationsAsRead.loading"
					@click="markAllNotificationsAsRead.submit()"
				>
					<template #prefix><FeatherIcon name="check-circle" class="w-4" /></template>
					{{ __("Mark all as read") }}
				</Button>
			</div>
		</template>
		<template #body>
			<div class="w-full px-4 pb-24 pt-4 lg:px-6">
				<div class="mx-auto w-full max-w-[720px] overflow-hidden rounded-2xl border border-line bg-white">
					<button
						v-for="item in items"
						:key="item.name"
						type="button"
						:class="[
							'flex w-full flex-row items-start gap-3 border-b border-[#F1F3F0] px-4 py-3.5 text-left last:border-0 hover:bg-gray-50',
							item.read ? 'bg-white' : 'bg-brand-50',
						]"
						@click="openItem(item)"
					>
						<span :class="['mt-2 h-2 w-2 flex-none rounded-full', item.read ? 'bg-gray-300' : 'bg-brand-600']"></span>
						<EmployeeAvatar :userID="item.from_user" size="lg" />
						<span class="flex flex-1 flex-col gap-0.5">
							<span class="text-sm text-ink" v-html="item.message"></span>
							<span class="text-xs text-gray-600">{{ dayjs(item.creation).fromNow() }}</span>
						</span>
					</button>
					<div v-if="notifications.fetched && !items.length" class="px-4 py-10 text-center text-sm text-gray-700">
						{{ __("You have no notifications") }}
					</div>
				</div>
				<div v-if="hasMore" class="mx-auto mt-3 flex w-full max-w-[720px]">
					<Button variant="outline" class="ml-auto" :loading="notifications.loading" @click="loadMore">
						{{ __("Load more") }}
					</Button>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { useRouter } from "vue-router"
import { FeatherIcon } from "frappe-ui"
import { computed, inject, onMounted, ref } from "vue"

import BaseLayout from "@/components/BaseLayout.vue"
import EmployeeAvatar from "@/components/EmployeeAvatar.vue"

import {
	arePushNotificationsEnabled,
	markAllNotificationsAsRead,
	markNotificationAsRead,
	notificationRoute,
	notifications,
	unreadNotificationsCount,
} from "@/data/notifications"

const dayjs = inject("$dayjs")
const router = useRouter()
const __ = inject("$translate")
const PAGE = 20
const limit = ref(PAGE)

const allowPushNotifications = computed(
	() => window.frappe?.boot.push_relay_server_url && arePushNotificationsEnabled.data
)

const items = computed(() => notifications.data || [])
const hasMore = computed(() => items.value.length >= limit.value)

function openItem(item) {
	if (!item.read) {
		item.read = 1
		markNotificationAsRead.submit({ name: item.name })
	}
	const route = notificationRoute(item)
	if (route) router.push(route)
}

function loadMore() {
	limit.value += PAGE
	notifications.submit({ start: 0, limit: limit.value })
}

onMounted(() => notifications.submit({ start: 0, limit: limit.value }))
</script>
