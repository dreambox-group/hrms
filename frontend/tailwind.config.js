import frappeUIPreset from "frappe-ui/src/tailwind/preset"
export default {
	presets: [frappeUIPreset],
	content: [
		"./index.html",
		"./src/**/*.{vue,js,ts,jsx,tsx}",
		"./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
		"../node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			// Drea Design System v0.8 (Vibe base): one blue for actions, grey for the rest.
			// "brand" is the action blue; the class names stay so screens keep working.
			colors: {
				brand: {
					50: "#F0F7FF", // highlight: selected row, info box
					100: "#CCE5FF", // selected
					300: "#AED4FC", // info border
					600: "#0073EA", // primary: main button, selected tab, focus ring
					700: "#0060B9", // primary hover, link
					800: "#004C94", // text on light blue
				},
				ink: "#323338", // main text
				page: "#F6F7FB", // page background
				line: "#D0D4E4", // lines around cards and tables
			},
			fontFamily: {
				sans: ["Figtree", "Roboto", "Segoe UI", "system-ui", "sans-serif"],
				title: ["Poppins", "Figtree", "Segoe UI", "system-ui", "sans-serif"],
			},
			screens: {
				standalone: {
					raw: "(display-mode: standalone)",
				},
			},
			padding: {
				"safe-top": "env(safe-area-inset-top)",
				"safe-right": "env(safe-area-inset-right)",
				"safe-bottom": "env(safe-area-inset-bottom)",
				"safe-left": "env(safe-area-inset-left)",
			},
		},
	},
	plugins: [],
}
