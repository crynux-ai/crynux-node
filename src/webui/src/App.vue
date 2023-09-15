<script setup>
import { RouterView } from 'vue-router'
import v1 from './api/v1/v1'
import { message } from 'ant-design-vue'
const [messageApi, contextHolder] = message.useMessage()

const defaultErrorHandler = () => {
  messageApi.error('Unexpected server error. Please try again later.')
}

v1.apiServerErrorHandler = defaultErrorHandler
v1.apiUnknownErrorHandler = defaultErrorHandler
</script>

<template>
  <context-holder />
  <RouterView />
</template>
<style lang="stylus">
body
    background #f5f5f5
</style>
<style scoped></style>
