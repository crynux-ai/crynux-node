<script setup>
import { computed, h, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { PauseCircleOutlined, LogoutOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import EditAccount from './edit-account.vue'

import systemAPI from '../api/v1/system'
import nodeAPI from '../api/v1/node'
import taskAPI from '../api/v1/task'
import accountAPI from '../api/v1/account'

const accountEditor = ref(null)

const systemInfo = reactive({
  gpu: {
    usage: 0,
    model: '',
    vram_used: 0,
    vram_total: 0
  },
  cpu: {
    usage: 0,
    num_cores: 0,
    frequency: 0
  },
  memory: {
    available: 0,
    total: 0
  },
  disk: {
    base_models: 0,
    lora_models: 0,
    logs: 0
  }
})

const nodeStatus = reactive({
  status: '',
  message: '',
  tx_status: '',
  tx_error: ''
})

const accountStatus = reactive({
  address: '',
  eth_balance: 0,
  cnx_balance: 0
})

const taskStatus = reactive({
  status: 'waiting',
  num_today: 0,
  num_total: 0
})

const shortAddress = computed(() => {
  if (accountStatus.address === '') {
    return 'N/A'
  } else {
    return (
      accountStatus.address.substring(0, 6) +
      '...' +
      accountStatus.address.substring(accountStatus.address.length - 4)
    )
  }
})

const toEtherValue = (bigNum) => {
  if (bigNum === 0) return 0
  return bigNum.dividedBy(1e18).toString()
}

let systemUpdateInterval
onMounted(async () => {
  await updateSystemInfo()
  systemUpdateInterval = setInterval(async () => {
    if (isTxSending.value) return
    await updateSystemInfo()
  }, 2000)

  if (accountStatus.address === '') {
    accountEditor.value.showModal()
  }
})
onBeforeUnmount(() => {
  clearInterval(systemUpdateInterval)
})

let isTxSending = ref(false)

const updateSystemInfo = async () => {
  const systemResp = await systemAPI.getSystemInfo()
  Object.assign(systemInfo, systemResp)

  const nodeResp = await nodeAPI.getNodeStatus()
  Object.assign(nodeStatus, nodeResp)

  const accountResp = await accountAPI.getAccountInfo()
  Object.assign(accountStatus, accountResp)

  const taskResp = await taskAPI.getTaskRunningStatus()
  Object.assign(taskStatus, taskResp)
}

const sendNodeAction = async (action) => {
  isTxSending.value = true
  try {
    await nodeAPI.sendNodeAction(action)
    await updateSystemInfo()
  } finally {
    isTxSending.value = false
  }
}
</script>

<template>
  <a-row style="height: 140px"></a-row>
  <a-row>
    <a-col :span="12" :offset="6" :style="{ height: '100px' }">
      <a-alert
        message="System is initializing. This may take a while, please be patient..."
        :style="{ 'text-align': 'center' }"
        v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING"
      ></a-alert>
      <a-alert
        type="error"
        :message="'Node error: ' + nodeStatus.message + '. Please restart the Docker container.'"
        :style="{ 'text-align': 'center' }"
        v-if="nodeStatus.status === nodeAPI.NODE_STATUS_ERROR"
      ></a-alert>
      <a-alert
        type="error"
        :message="'Transaction error: ' + nodeStatus.tx_error + '. Please try again later.'"
        :style="{ 'text-align': 'center' }"
        v-if="nodeStatus.tx_status === nodeAPI.TX_STATUS_ERROR"
      ></a-alert>
      <a-alert
        message="Waiting for the Blockchain confirmation..."
        :style="{ 'text-align': 'center' }"
        v-if="nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
      ></a-alert>
    </a-col>
  </a-row>
  <a-row :gutter="16">
    <a-col :span="4" :offset="3">
      <a-card title="Node Status" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="12">
            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              v-if="nodeStatus.status === nodeAPI.NODE_STATUS_RUNNING"
            />
            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              status="exception"
              v-if="nodeStatus.status === nodeAPI.NODE_STATUS_ERROR"
            >
            </a-progress>
            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              :stroke-color="'lightgray'"
              v-if="
                [
                  nodeAPI.NODE_STATUS_PAUSED,
                  nodeAPI.NODE_STATUS_STOPPED,
                  nodeAPI.NODE_STATUS_PENDING
                ].indexOf(nodeStatus.status) !== -1
              "
            >
              <template #format="percent">
                <span style="font-size: 14px; color: lightgray">
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING"
                    >Preparing</span
                  >
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PAUSED">Paused</span>
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_STOPPED">Stopped</span>
                </span>
              </template>
            </a-progress>
            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              :stroke-color="'cornflowerblue'"
              v-if="
                [nodeAPI.NODE_STATUS_PENDING, nodeAPI.NODE_STATUS_INITIALIZING].indexOf(
                  nodeStatus.status
                ) !== -1
              "
            >
              <template #format="percent">
                <span style="font-size: 14px; color: cornflowerblue">
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PENDING">Stopping</span>
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING"
                    >Preparing</span
                  >
                </span>
              </template>
            </a-progress>
          </a-col>
          <a-col :span="12">
            <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_RUNNING">
              <a-button
                :icon="h(PauseCircleOutlined)"
                @click="sendNodeAction('pause')"
                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                >Pause</a-button
              >
            </div>
            <div
              class="node-op-btn"
              style="margin-top: 8px"
              v-if="nodeStatus.status === nodeAPI.NODE_STATUS_RUNNING"
            >
              <a-button
                :icon="h(LogoutOutlined)"
                @click="sendNodeAction('stop')"
                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                >Stop</a-button
              >
            </div>
            <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_STOPPED">
              <a-button
                type="primary"
                :icon="h(PlayCircleOutlined)"
                @click="sendNodeAction('start')"
                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                >Start</a-button
              >
            </div>
            <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PAUSED">
              <a-button
                type="primary"
                :icon="h(PlayCircleOutlined)"
                @click="sendNodeAction('resume')"
                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                >Resume</a-button
              >
            </div>
            <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING">
              <a-button type="primary" :icon="h(PlayCircleOutlined)" disabled>Start</a-button>
            </div>
          </a-col>
        </a-row>
      </a-card>
    </a-col>

    <a-col :span="8">
      <a-card title="Wallet" :bordered="false" style="height: 100%">
        <template #extra>
          <edit-account
            ref="accountEditor"
            :account-status="accountStatus"
            @private-key-updated="updateSystemInfo"
          ></edit-account>
        </template>
        <a-row>
          <a-col :span="12">
            <a-statistic title="Address" :value="shortAddress"></a-statistic>
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="ETH"
              :precision="2"
              :value="toEtherValue(accountStatus.eth_balance)"
            ></a-statistic>
          </a-col>
          <a-col :span="6">
            <a-statistic
              title="CNX"
              :precision="2"
              :value="toEtherValue(accountStatus.cnx_balance)"
            ></a-statistic>
          </a-col>
        </a-row>
      </a-card>
    </a-col>

    <a-col :span="6">
      <a-card title="Task Execution" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="8">
            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              :stroke-color="'cornflowerblue'"
              v-if="taskStatus.status === 'idle'"
            >
              <template #format="percent">
                <span style="font-size: 14px; color: cornflowerblue">Idle</span>
              </template>
            </a-progress>

            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              :stroke-color="'lightgray'"
              v-if="taskStatus.status === 'waiting'"
            >
              <template #format="percent">
                <span style="font-size: 14px; color: lightgray">Waiting</span>
              </template>
            </a-progress>

            <a-progress
              type="circle"
              :size="70"
              :percent="100"
              status="success"
              v-if="taskStatus.status === 'running'"
            >
              <template #format="percent">
                <span style="font-size: 14px">Running</span>
              </template>
            </a-progress>
          </a-col>
          <a-col :span="8">
            <a-statistic title="Today" :precision="0" :value="taskStatus.num_today"></a-statistic>
          </a-col>
          <a-col :span="8">
            <a-statistic title="Total" :precision="0" :value="taskStatus.num_total"></a-statistic>
          </a-col>
        </a-row>
      </a-card>
    </a-col>
  </a-row>
  <a-row :gutter="16" style="margin-top: 16px">
    <a-col :span="6" :offset="3">
      <a-card title="GPU" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="8">
            <a-progress type="dashboard" :size="80" :percent="systemInfo.gpu.usage" />
          </a-col>
          <a-col :span="16">
            <a-row>
              <a-col :span="24">
                <a-statistic :value="systemInfo.gpu.model" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">Card Model</span></template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="12">
                <a-statistic
                  :value="systemInfo.gpu.vram_used"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">VRAM Used</span></template>
                  <template #suffix>MB</template>
                </a-statistic>
              </a-col>
              <a-col :span="12">
                <a-statistic
                  :value="systemInfo.gpu.vram_total"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">VRAM Total</span></template>
                  <template #suffix>MB</template>
                </a-statistic>
              </a-col>
            </a-row>
          </a-col>
        </a-row>
      </a-card>
    </a-col>
    <a-col :span="4">
      <a-card title="CPU" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="12">
            <a-progress type="dashboard" :size="80" :percent="systemInfo.cpu.usage" />
          </a-col>
          <a-col :span="12">
            <a-row>
              <a-col :span="24">
                <a-statistic
                  :value="systemInfo.cpu.num_cores"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">Num of Cores</span></template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="24">
                <a-statistic
                  :value="systemInfo.cpu.frequency"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">Frequency</span></template>
                  <template #suffix>MHz</template>
                </a-statistic>
              </a-col>
            </a-row>
          </a-col>
        </a-row>
      </a-card>
    </a-col>
    <a-col :span="4">
      <a-card title="Memory" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="12">
            <a-progress
              type="dashboard"
              :size="80"
              :percent="
                Math.round(
                  ((systemInfo.memory.total - systemInfo.memory.available) /
                    systemInfo.memory.total) *
                    100
                )
              "
            />
          </a-col>
          <a-col :span="12">
            <a-row>
              <a-col :span="24">
                <a-statistic
                  :value="systemInfo.memory.total - systemInfo.memory.available"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">RAM Used</span></template>
                  <template #suffix>MB</template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="24">
                <a-statistic
                  :value="systemInfo.memory.total"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">RAM Total</span></template>
                  <template #suffix>MB</template>
                </a-statistic>
              </a-col>
            </a-row>
          </a-col>
        </a-row>
      </a-card>
    </a-col>
    <a-col :span="4">
      <a-card title="Disk" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="12">
            <a-statistic
              :value="systemInfo.disk.base_models"
              :value-style="{ 'font-size': '14px' }"
            >
              <template #title><span style="font-size: 12px">Base Models</span></template>
              <template #suffix>GB</template>
            </a-statistic>
          </a-col>
          <a-col :span="12">
            <a-statistic
              :value="systemInfo.disk.lora_models"
              :value-style="{ 'font-size': '14px' }"
            >
              <template #title><span style="font-size: 12px">Lora Models</span></template>
              <template #suffix>MB</template>
            </a-statistic>
          </a-col>
        </a-row>
        <a-row style="margin-top: 12px">
          <a-col :span="12">
            <a-statistic :value="systemInfo.disk.logs" :value-style="{ 'font-size': '14px' }">
              <template #title><span style="font-size: 12px">Logs</span></template>
              <template #suffix>KB</template>
            </a-statistic>
          </a-col>
        </a-row>
      </a-card>
    </a-col>
  </a-row>
  <a-row style="margin-top: 64px">
    <a-col :span="14" :offset="5" style="text-align: center">
      <a-space class="footer-links">
        <a-typography-link href="https://crynux.ai" target="_blank">Home</a-typography-link>
        &nbsp;|&nbsp;
        <a-typography-link href="https://docs.crynux.ai" target="_blank">Docs</a-typography-link>
        &nbsp;|&nbsp;
        <a-typography-link href="https://github.com/crynux-ai" target="_blank"
          >GitHub</a-typography-link
        >
        &nbsp;|&nbsp;
        <a-typography-link href="https://blog.crynux.ai" target="_blank">Blog</a-typography-link>
        &nbsp;|&nbsp;
        <a-typography-link href="https://twitter.com/crynux" target="_blank"
          >Twitter</a-typography-link
        >
        &nbsp;|&nbsp;
        <a-typography-link href="https://discord.gg/crynux" target="_blank"
          >Discord</a-typography-link
        >
      </a-space>
    </a-col>
  </a-row>
  <a-row style="margin-top: 36px">
    <a-col :span="24" style="text-align: center">
      <img class="footer-logo" src="./logo-full-black.png" width="140" alt="Crynux logo" />
    </a-col>
  </a-row>
</template>

<style lang="stylus">
.ant-row
    margin-left 0!important
    margin-right 0!important
</style>
<style scoped lang="stylus">
.footer-links
    color #666
    a
        color #666
        &:hover
            text-decoration underline
.footer-logo
    opacity 0.5
</style>
