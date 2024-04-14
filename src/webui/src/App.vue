<script setup>
import { RouterView } from 'vue-router'
import v1 from './api/v1/v1'
import { message } from 'ant-design-vue'
import { onBeforeUnmount, onMounted, ref, h } from 'vue'
import { BulbOutlined } from '@ant-design/icons-vue'
const [messageApi, contextHolder] = message.useMessage()

const defaultErrorHandler = (msg) => {
  if(!/ContractError/.test(msg)) {
    messageApi.error('Unexpected server error. Please try again later.')
  }
}

v1.apiServerErrorHandler = defaultErrorHandler
v1.apiUnknownErrorHandler = defaultErrorHandler

const vantaRef = ref(null)

let wavesEffect = null

const toggleWaves = () => {
  if (wavesEffect === null) {
    startWaves()
  } else {
    stopWaves()
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

onMounted(() => {
  startWaves()
})
onBeforeUnmount(() => {
  stopWaves()
})
</script>

<template>
  <div id="bg-container" ref="vantaRef">
    <div id="content-container">
      <div id="toolbar">
        <a-button size="large" type="text" :icon="h(BulbOutlined)" @click="toggleWaves" ghost :style="{'color': 'white'}"/>
      </div>
      <context-holder />
      <RouterView />
    </div>
  </div>
</template>

<style lang="stylus" scoped>
#bg-container,
    #content-container
    position relative
    width 100%
    height 100%

#toolbar
  position absolute
  top 6px
  right 6px
</style>
