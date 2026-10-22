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
			// Drea HRIS: mint from the logo, a deep green for actions, a soft grey page
			colors: {
				brand: {
					50: "#F1FBF6",
					100: "#DDF5EA",
					300: "#8FE3C0",
					600: "#0B7A5C",
					700: "#075A44",
					800: "#0B5C45",
				},
				ink: "#16181A",
				page: "#F4F5F3",
				line: "#E4E7E3",
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
