<script setup>
import { ref } from 'vue'

const modalVisible = ref(false)
const activeImportType = ref('private-key')
const privateKeyInput = ref('')
const keystoreInput = ref('')
const keystorePassphraseInput = ref('')
const isLoading = ref(false)

const props = defineProps(['accountStatus'])

const showModal = () => {
  modalVisible.value = true
}

const hideModal = () => {
  modalVisible.value = false
}

const changeAccount = () => {}

defineExpose({ showModal })
</script>

<template>
  <a href="javascript:void(0)" @click="showModal">Edit</a>
  <a-modal
    :visible="modalVisible"
    title="Node Wallet"
    @ok="hideModal"
    @cancel="hideModal"
    width="700px"
    :destroy-on-close="true"
    :mask-closable="false"
  >
    <a-alert
      message="A wallet with enough ETH(>0.01) and CNX(>400) must be provided to the node"
      type="info"
      style="margin-top: 16px"
      v-if="props.accountStatus.address === ''"
    />

    <a-tabs v-model:activeKey="activeImportType">
      <a-tab-pane key="private-key" tab="Private Key">
        <a-textarea
          v-model:value="privateKeyInput"
          placeholder="Paste the private key"
          :auto-size="{ minRows: 5, maxRows: 5 }"
        ></a-textarea>
      </a-tab-pane>
      <a-tab-pane key="keystore" tab="Keystore">
        <a-textarea
          v-model:value="keystoreInput"
          placeholder="Paste the keystore json"
          :auto-size="{ minRows: 5, maxRows: 5 }"
        ></a-textarea>
        <a-input-password
          v-model:value="keystorePassphraseInput"
          placeholder="Keystore passphrase"
          style="margin-top: 12px"
        />
      </a-tab-pane>
    </a-tabs>
    <template #footer>
      <a-button key="submit" type="primary" :loading="isLoading" @click="changeAccount"
        >Submit</a-button
      >
    </template>
  </a-modal>
</template>

<style scoped lang="stylus"></style>
