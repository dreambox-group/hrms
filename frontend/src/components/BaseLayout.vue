<template>
	<ion-page>
		<ion-header class="ion-no-border">
			<div class="w-full border-b border-line bg-white">
				<div class="mx-auto flex w-full max-w-[1200px] flex-row items-center gap-4 px-4 py-2.5 lg:gap-8 lg:px-6">
					<router-link :to="{ name: 'Home' }" class="flex flex-row items-center gap-2.5 text-ink">
						<DreaLogo class="h-8 w-8" />
						<span class="text-lg font-bold tracking-tight">{{ __("Drea One") }}</span>
					</router-link>
					<nav class="hidden flex-row items-center gap-1 lg:flex" :aria-label="__('Main')">
						<router-link
							v-for="item in sections"
							:key="item.route"
							:to="item.route"
							:class="[
								'rounded-lg px-3.5 py-2 text-sm',
								isActive(item)
									? 'bg-brand-100 font-semibold text-brand-800'
									: 'font-medium text-gray-700 hover:bg-gray-100 hover:text-ink',
							]"
						>
							{{ item.title }}
						</router-link>
					</nav>
					<div class="ml-auto flex flex-row items-center gap-2">
						<NotificationBell />
						<router-link :to="{ name: 'Profile' }" :aria-label="__('Profile')" class="flex items-center">
							<Avatar :image="user.data.user_image" :label="user.data.first_name" size="xl" />
						</router-link>
					</div>
				</div>
			</div>
		</ion-header>

		<ion-content class="ion-no-padding drea-page">
			<div class="mx-auto flex w-full max-w-[1200px] flex-col">
				<div v-if="props.pageTitle || props.backTo" class="flex flex-col gap-2 px-4 pt-6 lg:px-6 lg:pt-8">
					<router-link
						v-if="props.backTo"
						:to="props.backTo"
						class="flex flex-row items-center gap-1 self-start text-sm font-medium text-gray-700 hover:text-ink"
					>
						<FeatherIcon name="chevron-left" class="h-4 w-4" />
						{{ props.backLabel || __("Back") }}
					</router-link>
					<div class="flex flex-row flex-wrap items-center justify-between gap-3">
						<h1 v-if="props.pageTitle" class="text-2xl font-bold tracking-tight text-ink lg:text-3xl">
							{{ props.pageTitle }}
						</h1>
						<slot name="actions"></slot>
					</div>
				</div>
				<slot name="body"></slot>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { IonHeader, IonContent, IonPage } from "@ionic/vue"
import { FeatherIcon, Avatar } from "frappe-ui"
import { useRoute } from "vue-router"
import { inject } from "vue"

import DreaLogo from "@/components/icons/DreaLogo.vue"
import NotificationBell from "@/components/NotificationBell.vue"
import { useMainSections } from "@/utils/navigation"

const user = inject("$user")
const __ = inject("$translate")
const route = useRoute()
const sections = useMainSections(__)

const props = defineProps({
	// shown as the page's heading, under the bar; the bar always says Drea One
	pageTitle: {
		type: String,
		required: false,
		default: "",
	},
	backTo: {
		type: [String, Object],
		required: false,
		default: null,
	},
	backLabel: {
		type: String,
		required: false,
		default: "",
	},
	// kept for older callers: every page now uses the same width
	wide: {
		type: Boolean,
		default: false,
	},
})

function isActive(item) {
	if (item.route === "/home") return route.path === "/home" || route.path === "/approvals"
	if (item.route === "/dashboard/leaves")
		return route.path.startsWith(item.route) || route.path.startsWith("/leave-applications")
	if (item.route === "/dashboard/attendance")
		return route.path.startsWith(item.route) || route.path.startsWith("/employee-checkins")
	return route.path.startsWith(item.route)
}
</script>
