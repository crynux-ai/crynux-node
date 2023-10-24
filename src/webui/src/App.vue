<script setup>
import { RouterView } from 'vue-router'
import v1 from './api/v1/v1'
import { message } from 'ant-design-vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
const [messageApi, contextHolder] = message.useMessage()

const defaultErrorHandler = () => {
  messageApi.error('Unexpected server error. Please try again later.')
}

v1.apiServerErrorHandler = defaultErrorHandler
v1.apiUnknownErrorHandler = defaultErrorHandler

const vantaRef = ref(null)

let wavesEffect = null
onMounted(() => {
  wavesEffect = VANTA.WAVES({
    el: vantaRef.value,
    waveSpeed: 0.7,
    zoom: 1,
    waveHeight: 10,
    shininess: 50
  })
})
onBeforeUnmount(() => {
  if (wavesEffect) {
    wavesEffect.destroy()
  }
})
</script>

<template>
  <div id="bg-container" ref="vantaRef">
    <div id="content-container">
      <context-holder />
      <RouterView />
    </div>
  </div>
</template>
<style lang="stylus"></style>
<style lang="stylus" scoped>
#bg-container,
    #content-container
    position relative
    width 100%
    height 100%
</style>
