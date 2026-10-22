<template>
	<ion-tab-bar
		slot="bottom"
		class="bg-white border-t border-line w-full lg:hidden py-1.5 pb-2 standalone:pb-safe-bottom"
	>
		<ion-tab-button
			v-for="item in tabItems"
			:key="item.title"
			:tab="item.title"
			:href="item.route"
			:class="[
				'bg-white text-xs space-y-1 transition active:scale-95',
				route.path.startsWith(item.route)
					? 'text-brand-800 font-semibold'
					: 'text-gray-600 font-medium',
			]"
		>
			<component :is="item.icon" class="h-5 w-5" />
			<div>{{ item.title }}</div>
		</ion-tab-button>
	</ion-tab-bar>
</template>

<script setup>
import { useRoute } from "vue-router"

import { IonTabBar, IonTabButton, IonLabel } from "@ionic/vue"

import { inject } from "vue"

import { useMainSections } from "@/utils/navigation"

const __ = inject("$translate")

const route = useRoute()

// on wide screens these sections are in the top bar instead (BaseLayout)
const tabItems = useMainSections(__)
</script>
