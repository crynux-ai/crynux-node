import log from '@/log/log.js'

const localStorageAndPythonStorage = {
    getItem: async (key) => {
        if (window.qtBackend) {
            log.debug("reading state from QT backend: " + key)
            const val = await window.qtBackend.get_settings_item(key)
            log.debug("value from QT: " + val)
            return val
        }

        if (window.localStorage) {
            log.debug("reading state from LocalStorage: " + key)
            return window.localStorage.getItem(key)
        }

        return ""
    },
    setItem: async (key, value) => {

        log.debug("set state item")

        if(window.qtBackend) {
            log.debug("set state item to QT backend")
            log.debug(key + ":" + value)
            return window.qtBackend.set_settings_item(key, value)
        }

        if(window.localStorage) {
            return window.localStorage.setItem(key, value)
        }
    }
}

export default localStorageAndPythonStorage
