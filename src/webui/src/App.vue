<script setup>
import { RouterView } from 'vue-router'
import V1Client from '@/api/v1/v1'
import { Grid, message, Modal } from 'ant-design-vue'
import { onBeforeUnmount, onMounted, ref, h, computed, createVNode } from 'vue'
import { BulbOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue'
import { useSystemStore } from '@/stores/system'

const [messageApi, contextHolder] = message.useMessage()

const systemStore = useSystemStore()

const defaultErrorHandler = (msg) => {
    if (!/ContractError/.test(msg)) {
        messageApi.error('Network error. Will try again later.')
        console.error('Default error handler: ', msg)
    }
}

V1Client.prototype.apiServerErrorHandler = defaultErrorHandler
V1Client.prototype.apiUnknownErrorHandler = defaultErrorHandler
V1Client.prototype.apiForbiddenErrorHandler = () => {
    messageApi.error('Request is forbidden. Will try again later.')
    console.error('Default forbidden error handler')
}

const vantaRef = ref(null)

let wavesEffect = null

const toggleWaves = () => {
    if (wavesEffect === null) {
        startWaves()
        systemStore.setShowWaveBg(true)
    } else {
        stopWaves()
        systemStore.setShowWaveBg(false)
    }
}

const startWaves = () => {
    if (wavesEffect === null) {
        wavesEffect = VANTA.WAVES({
            el: vantaRef.value,
            waveSpeed: 0.7,
            zoom: 1,
            waveHeight: 10,
            shininess: 50
        })
    }
}

const stopWaves = () => {
    if (wavesEffect !== null) {
        wavesEffect.destroy()
        wavesEffect = null
    }
}

const useBreakpoint = Grid.useBreakpoint
const screens = useBreakpoint()
const screenClasses = computed(() => {
    let classes = ['content-container']
    for (let v in screens.value) {
        if (screens.value[v]) {
            classes.push(v)
        }
    }

    return classes
})

// This one is only called from the Python side
const closeWindow = () => {
    if(systemStore.showMinimizedNotification) {
        Modal.confirm({
            title: 'Node will be minimized',
            icon: createVNode(ExclamationCircleOutlined),
            content: "Crynux Node will still be running in the background. Use the system tray to exit it.",
            onOk() {
                systemStore.setShowMinimizedNotification(false)
                window.qtBackend.hide_window()
            },
            onCancel() {}
        })
    } else {
        window.qtBackend.hide_window()
    }
}

defineExpose({
  closeWindow,
})

onMounted(() => {
    if (systemStore.showWaveBg) {
        startWaves()
    }
})
onBeforeUnmount(() => {
    stopWaves()
})
</script>

<template>
    <div id="bg-container" ref="vantaRef">
        <div id="content-scroll-wrapper">
            <div id="content-container" :class="screenClasses">
                <div id="toolbar">
                    <a-button size="large" type="text" :icon="h(BulbOutlined)" @click="toggleWaves" ghost
                              :style="{'color': 'white'}" />
                </div>
                <context-holder />
                <RouterView />
            </div>
        </div>
    </div>
</template>

<style lang="stylus" scoped>
#bg-container
    position relative
    width 100%
    height 100%

#content-scroll-wrapper
    position absolute
    width 100%
    height 100%
    overflow-x hidden
    overflow-y auto

#content-container
    position relative
    width 100%

#toolbar
    position absolute
    top 6px
    right 6px
</style>
