import { reactive } from "vue"

const subscribed = reactive({})

// returns a function that stops listening (call it when the page goes away)
export function useListUpdate(socket, doctype, callback) {
	subscribe(socket, doctype)
	const handler = (data) => {
		if (data.doctype == doctype) {
			callback(data.name)
		}
	}
	socket.on("list_update", handler)
	return () => socket.off("list_update", handler)
}

function subscribe(socket, doctype) {
	if (subscribed[doctype]) return

	socket.emit("doctype_subscribe", doctype)
	subscribed[doctype] = true
}
