<script setup>
import { ref } from 'vue'
import accountAPI from '../api/v1/account'
import { CopyOutlined, SmileTwoTone } from '@ant-design/icons-vue'
import config from '../config.json'

const props = defineProps(['oldWalletExists']);
const emits = defineEmits(['startCreateWallet', 'closeCreateWallet', 'privateKeyUpdated']);

const modalVisible = ref(false);
const isLoading = ref(false);

const startStep = 'create'
const step = ref(startStep);

const privateKey = ref('');
const address = ref('');

const start = () => {
    emits('startCreateWallet');
    step.value = startStep;
    modalVisible.value = true;
};

const cancel = () => {
    modalVisible.value = false;
    emits('closeCreateWallet');
};

const createAccount = async () => {
    isLoading.value = true;

    try {
        const wallet = await accountAPI.createAccount();
        emits('privateKeyUpdated');
        privateKey.value = wallet.key;
        address.value = wallet.address;
        step.value = 'backup';
    } finally {
        isLoading.value = false;
    }

};

const copyText = async (text) => {
    return navigator.clipboard.writeText(text);
};

</script>
<template>
    <a-button
        key="create"
        @click="start"
        :style="{'float': 'left'}"
        >Create New Wallet</a-button
      >

      <a-modal
    :visible="modalVisible"
    title="Create New Wallet"
    @cancel="cancel"
    @close="cancel"
    width="700px"
    :destroy-on-close="true"
    :mask-closable="false"
  >
  <a-result
    v-if="step === 'create' && !props.oldWalletExists"
      title="A new Ethereum wallet will be created."
      sub-title="The private key of the wallet will be saved in the node. You will have a chance to backup the private key in the next step."
      ></a-result>

      <a-result
    v-if="step === 'create' && props.oldWalletExists"
      title="Your old wallet will be lost!"
      sub-title="You have an old private key saved in the node. Creating new wallet will cause the old private key being overwritten. Please double check your backup before proceeding. A new private key will be created, and you will have a chance to backup the new private key in the next step."
      ></a-result>

    <a-result
        v-if="step === 'backup'"
        title="Backup your private key"
        sub-title="Copy your private key to a file and save it to somewhere safe."
        >
        <template #extra>
            <a-input-group compact>
      <a-input v-model:value="privateKey" style="width: calc(100% - 200px)" readonly addon-before="Private key"/>
      <a-tooltip title="copy private key">
        <a-button @click="copyText(privateKey)">
          <template #icon><CopyOutlined /></template>
        </a-button>
      </a-tooltip>
    </a-input-group>
        </template>
    </a-result>

    <a-result
        v-if="step === 'discord'"
        title="Get test ETH and CNX tokens from Discord"
        sub-title="Some test tokens are required to start the node, You could join the Discord Server of Crynux to get the test tokens for free."
    >
    <template #icon>
      <smile-twoTone />
    </template>
    <template #extra>
        <a-space direction="vertical" size="large" :style="{'width': '100%'}">
            <a-button
                type="primary"
                :href="config.discord_link"
                target="_blank"
            >Go to the Crynux Discord server</a-button>

            <a-input-group compact>
                <a-input v-model:value="config.discord_link" style="width: calc(100% - 200px)" readonly addon-before="Crynux Discord"/>
                <a-tooltip title="Copy Discord link">
                    <a-button @click="copyText(config.discord_link)">
                    <template #icon><CopyOutlined /></template>
                    </a-button>
                </a-tooltip>
            </a-input-group>

            <a-input-group compact>
                <a-input v-model:value="address" style="width: calc(100% - 200px)" readonly addon-before="Wallet Address"/>
                <a-tooltip title="Copy wallet address">
                    <a-button @click="copyText(address)">
                    <template #icon><CopyOutlined /></template>
                    </a-button>
                </a-tooltip>
            </a-input-group>
        </a-space>
        </template>
    </a-result>

  <template #footer>
    <a-button
        v-if="step === 'create'"
        key="cancel"
        :loading="isLoading"
        @click="cancel"

        >Cancel</a-button>
      <a-button
      v-if="step === 'create'"
        key="submit"
        type="primary"
        :loading="isLoading"
        @click="createAccount"
        >Create</a-button
      >
      <a-button
        v-if="step === 'backup'"
        key="backup"
        type="primary"
        @click="step='discord'"
        >Next</a-button>

      <a-button
        v-if="step === 'discord'"
        key="done"
        type="primary"
        @click="cancel"
        >Done</a-button>
    </template>
  </a-modal>
</template>
