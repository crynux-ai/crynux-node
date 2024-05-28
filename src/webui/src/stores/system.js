import { defineStore } from 'pinia'

export const useSystemStore = defineStore('system', {
    state: () => ({
        showWaveBg: true,
        showMinimizedNotification: true
    }),
    actions: {
        setShowWaveBg(show) {
            this.showWaveBg = show
        },
        setShowMinimizedNotification(show) {
            this.showMinimizedNotification = show
        }
    }
})
