<script setup>
import { computed, ref } from 'vue'
import accountAPI from '../api/v1/account'

const modalVisible = ref(false)
const activeImportType = ref('private-key')
const privateKeyInput = ref('')
const keystoreInput = ref('')
const keystorePassphraseInput = ref('')
const isLoading = ref(false)

const props = defineProps(['accountStatus'])
const emits = defineEmits(['privateKeyUpdated'])

const showModal = () => {
  modalVisible.value = true
}

const hideModal = () => {
  modalVisible.value = false
  privateKeyInput.value = ''
  keystoreInput.value = ''
  keystorePassphraseInput.value = ''
}

const readyToSubmit = computed(() => {
  if (activeImportType.value === 'private-key') {
    return privateKeyInput.value !== ''
  } else {
    return keystoreInput.value !== ''
  }
})

const apiError = ref(null)
const changeAccount = async () => {
  isLoading.value = true

  try {
    if (activeImportType.value === 'private-key') {
      await accountAPI.updatePrivateKey(privateKeyInput.value)
    } else {
      await accountAPI.updateKeystore(keystoreInput.value, keystorePassphraseInput.value)
    }

    emits('privateKeyUpdated')
    hideModal()
  } catch (e) {
    apiError.value = e
  }

  isLoading.value = false
}

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
    :closable="props.accountStatus.address !== ''"
  >
    <a-alert
      message="A wallet with enough ETH(>0.01) and CNX(>400) must be provided to the node"
      type="info"
      style="margin-top: 16px"
      v-if="props.accountStatus.address === '' && apiError === null"
    />

    <a-alert
      :message="apiError.data"
      type="error"
      style="margin-top: 16px"
      v-if="apiError !== null"
    />

    <a-tabs v-model:activeKey="activeImportType">
      <a-tab-pane key="private-key" tab="Private Key">
        <a-textarea
          v-model:value="privateKeyInput"
          placeholder="0x6666......(64 hex digits)......6666666"
          :auto-size="{ minRows: 5, maxRows: 5 }"
        ></a-textarea>
      </a-tab-pane>
      <a-tab-pane key="keystore" tab="Keystore">
        <a-textarea
          v-model:value="keystoreInput"
          placeholder='{"crypto":{"cipher":"aes-128-ctr","cipherparams":{"iv":"83dbcc02d8ccb40e466191a123791e0e"},"ciphertext":"d172bf743a674da9cdad04534d56926ef8358534d458fffccd4e6ad2fbde479c","kdf":"scrypt","kdfparams":{"dklen":32,"n":262144,"r" : 1,"p":8,"salt":"ab0c7876052600dd703518d6fc3fe8984592145b591fc8fb5c6d43190334ba19"},"mac":"2103ac29920d71da29f15d75b4a16dbe95cfd7ff8faea1056c33131d846e3097"},"id":"3198bc9c-6672-5ab3-d995-4942343ae5b6","version":3}'
          :auto-size="{ minRows: 5, maxRows: 5 }"
        ></a-textarea>
        <a-input-password
          v-model:value="keystorePassphraseInput"
          placeholder="Passphrase to unlock the pasted keystore (can be empty)"
          style="margin-top: 12px"
        />
      </a-tab-pane>
    </a-tabs>
    <template #footer>
      <a-button
        key="submit"
        type="primary"
        :loading="isLoading"
        :disabled="!readyToSubmit"
        @click="changeAccount"
        >Submit</a-button
      >
    </template>
  </a-modal>
</template>

<style scoped lang="stylus"></style>
