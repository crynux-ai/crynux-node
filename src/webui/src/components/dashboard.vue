<script setup>
import { computed, createVNode, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
    PauseCircleOutlined,
    LogoutOutlined,
    PlayCircleOutlined,
    ExclamationCircleOutlined,
    CopyOutlined
} from '@ant-design/icons-vue'
import { Grid, Modal } from 'ant-design-vue'
import EditAccount from './edit-account.vue'
import GithubButton from 'vue-github-button'

import SystemAPI from '../api/v1/system'
import NodeAPI from '../api/v1/node'
import TaskAPI from '../api/v1/task'
import AccountAPI from '../api/v1/account'
import config from '../config.json'
import logger from '../log/log'

const appVersion = APP_VERSION

const accountAPI = new AccountAPI()
const nodeAPI = new NodeAPI()
const systemAPI = new SystemAPI()
const taskAPI = new TaskAPI()

const accountEditor = ref(null)

const systemInfo = reactive({
    gpu: {
        usage: 0,
        model: '',
        vram_used_mb: 0,
        vram_total_mb: 0
    },
    cpu: {
        usage: 0,
        num_cores: 0,
        frequency_mhz: 0,
        description: ''
    },
    memory: {
        available_mb: 0,
        total_mb: 0
    },
    disk: {
        base_models: 0,
        lora_models: 0,
        logs: 0
    }
})

const nodeStatus = reactive({
    status: nodeAPI.NODE_STATUS_INITIALIZING,
    init_message: '',
    message: '',
    tx_status: '',
    tx_error: ''
})

const accountStatus = reactive({
    address: '',
    balance: 0
})

const taskStatus = reactive({
    status: 'waiting',
    num_today: 0,
    num_total: 0
})

let apiContinuousErrorCount = reactive({
    'account': 0,
    'node': 0,
    'system': 0,
    'task': 0
})

const apiErrorHandler = (apiName) => {
    return () => {
        apiContinuousErrorCount[apiName]++
        logger.error('API Error: ', apiName)
    }
}

const accountAPIErrorHandler = apiErrorHandler('account')
accountAPI.getHttpClient().apiServerErrorHandler = accountAPIErrorHandler
accountAPI.getHttpClient().apiUnknownErrorHandler = accountAPIErrorHandler
accountAPI.getHttpClient().apiForbiddenErrorHandler = accountAPIErrorHandler

const nodeAPIErrorHandler = apiErrorHandler('node')
nodeAPI.getHttpClient().apiServerErrorHandler = nodeAPIErrorHandler
nodeAPI.getHttpClient().apiUnknownErrorHandler = nodeAPIErrorHandler
nodeAPI.getHttpClient().apiForbiddenErrorHandler = nodeAPIErrorHandler

const systemAPIErrorHandler = apiErrorHandler('system')
systemAPI.getHttpClient().apiServerErrorHandler = systemAPIErrorHandler
systemAPI.getHttpClient().apiUnknownErrorHandler = systemAPIErrorHandler
systemAPI.getHttpClient().apiForbiddenErrorHandler = systemAPIErrorHandler

const taskAPIErrorHandler = apiErrorHandler('task')
taskAPI.getHttpClient().apiServerErrorHandler = taskAPIErrorHandler
taskAPI.getHttpClient().apiUnknownErrorHandler = taskAPIErrorHandler
taskAPI.getHttpClient().apiForbiddenErrorHandler = taskAPIErrorHandler

const shortAddress = computed(() => {
    if (accountStatus.address === '') {
        return 'N/A'
    } else {
        return (
            accountStatus.address.substring(0, 7) +
            '...' +
            accountStatus.address.substring(accountStatus.address.length - 5)
        )
    }
})

const toEtherValue = (bigNum) => {
    if (bigNum === 0) return 0

    const decimals = (bigNum / BigInt(1e18)).toString()

    let fractions = ((bigNum / BigInt(1e14)) % 10000n).toString()

    while (fractions.length < 4) {
        fractions = '0' + fractions
    }

    return decimals + '.' + fractions
}

const stakingMinimum = 4e20
const gasMinimum = 1e16

const ethEnoughForGas = () => {
    if (accountStatus.balance === 0) return false
    return accountStatus.balance >= gasMinimum
}

const ethEnough = () => {
    if (accountStatus.balance === 0) return false
    return accountStatus.balance >= (stakingMinimum + gasMinimum)
}

const privateKeyUpdated = async () => {
    logger.debug('received privateKeyUpdated')
    await updateUI()
}

let fixedBottomBar = ref(false)

const windowResized = () => {
    const bottomBar = document.getElementById("bottom-bar")
    if(!bottomBar)
        return

    const windowHeight = window.innerHeight
    const contentHeight = document.getElementById("content-container").offsetHeight
    const bottomBarHeight = bottomBar.offsetHeight

    const threshold = fixedBottomBar.value ? contentHeight + bottomBarHeight + 68 : contentHeight
    fixedBottomBar.value = windowHeight > threshold
}


let uiUpdateInterval = null
let uiUpdateCurrentTicket = null
onMounted(async () => {

    windowResized()
    addEventListener("resize", windowResized);

    try {
        await updateUI()
    } catch (e) {
        logger.error('First time UI update failed')
    }

    if (uiUpdateInterval != null) {
        clearInterval(uiUpdateInterval)
    }

    uiUpdateInterval = setInterval(updateUI, 5000)
})

onBeforeUnmount(() => {
    clearInterval(uiUpdateInterval)
    uiUpdateInterval = null
})

const updateUI = async () => {
    uiUpdateCurrentTicket = Date.now()

    try {
        await updateTaskStats(uiUpdateCurrentTicket)
    } catch (e) {
        logger.error("Updating task stats failed:")
        logger.error(e)
    }

    try {
        await updateUIWithTicket(uiUpdateCurrentTicket)
    } catch (e) {
        logger.error("Updating UI failed:")
        logger.error(e)
    }

    try {
        await updateSystemInfo(uiUpdateCurrentTicket)
    } catch (e) {
        logger.error("Updating system info failed:")
        logger.error(e)
    }
}

const updateUIWithTicket = async (ticket) => {

    logger.debug('[' + ticket + '] Updating UI')

    if (isTxSending.value) return
    await updateAccountInfo(ticket)

    if (ticket !== uiUpdateCurrentTicket) {
        logger.debug('[' + ticket + '] Ticket is old. Do not use this data to update UI.')
        return
    }

    if (accountStatus.address === '') {
        logger.debug('[' + ticket + '] Account address is empty. Show edit account dialog.')
        accountEditor.value.showModal()
    } else {
        logger.debug('[' + ticket + '] Account address is not empty. Continue updating network info.')
        await updateNetworkInfo(ticket)
    }
}

const updateAccountInfo = async (ticket) => {

    logger.debug('[' + ticket + '] Updating account info')

    const accountResp = await accountAPI.getAccountInfo()

    logger.debug('[' + ticket + '] Retrieved account address: ' + accountResp.address)

    apiContinuousErrorCount['account'] = 0

    if (ticket === uiUpdateCurrentTicket) {
        logger.debug('[' + ticket + '] Ticket is latest. Update the data.')
        Object.assign(accountStatus, accountResp)
    } else {
        logger.debug('[' + ticket + '] Ticket is old. Discard the response')
    }
}

const updateNetworkInfo = async (ticket) => {

    const nodeResp = await nodeAPI.getNodeStatus()
    apiContinuousErrorCount['node'] = 0

    if (ticket === uiUpdateCurrentTicket) {
        Object.assign(nodeStatus, nodeResp)
    }
}

const updateSystemInfo = async (ticket) => {
    const systemResp = await systemAPI.getSystemInfo()
    apiContinuousErrorCount['system'] = 0

    if (ticket === uiUpdateCurrentTicket) {
        Object.assign(systemInfo, systemResp)
    }
}

const updateTaskStats = async (ticket) => {
    const taskResp = await taskAPI.getTaskRunningStatus()
    apiContinuousErrorCount['task'] = 0

    if (ticket === uiUpdateCurrentTicket) {
        Object.assign(taskStatus, taskResp)
    }
}

let isTxSending = ref(false)
const sendNodeAction = async (action) => {
    if (isTxSending.value) {
        return
    }

    if (action === 'pause') {
        await sendNodeActionAfterConfirmation(
            action,
            'Are you sure to pause the node? You could resume the running later.'
        )
    } else if (action === 'stop') {
        await sendNodeActionAfterConfirmation(
            action,
            'Are you sure to stop the node? The staked tokens will be returned. You could start the node later.'
        )
    } else {
        await doSendNodeAction(action)
    }
}

const sendNodeActionAfterConfirmation = async (action, message) => {
    Modal.confirm({
        title: 'Confirm node operation',
        icon: createVNode(ExclamationCircleOutlined),
        content: message,
        onOk() {
            return doSendNodeAction(action)
        },

        onCancel() {
        }
    })
}

const doSendNodeAction = async (action) => {
    isTxSending.value = true
    try {
        await nodeAPI.sendNodeAction(action)
        await updateSystemInfo()
    } finally {
        isTxSending.value = false
    }
}

const useBreakpoint = Grid.useBreakpoint
const screens = useBreakpoint()

const getPercent = (num) => {
    if (num >= 100) {
        return 99
    }

    return num
}

const copyText = async (text) => {
    return navigator.clipboard.writeText(text)
}

</script>

<template>
    <a-row class="top-row"></a-row>
    <a-row>
        <a-col
            :xs="{ span: 22, offset: 1, order: 1 }"
            :sm="{ span: 22, offset: 1, order: 1 }"
            :md="{ span: 22, offset: 1, order: 1 }"
            :lg="{ span: 14, offset: 5, order: 1 }"
            :xl="{ span: 14, offset: 5, order: 1 }"
            :xxl="{ span: 14, offset: 5, order: 1 }"
        >
            <a-alert
                message="System is initializing..."
                class="top-alert"
                v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING && nodeStatus.init_message === ''"
            ></a-alert>
            <a-alert
                :message="nodeStatus.init_message"
                class="top-alert"
                v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING && nodeStatus.init_message !== ''"
            ></a-alert>
            <a-alert
                type="error"
                :message="nodeStatus.message"
                class="top-alert"
                v-if="nodeStatus.status === nodeAPI.NODE_STATUS_ERROR"
            ></a-alert>
            <a-alert
                type="error"
                :message="'Cannot get account info from node due to network error, retrying...'"
                class="top-alert"
                v-if="apiContinuousErrorCount['account'] >= 3"
            ></a-alert>
            <a-alert
                type="error"
                :message="'Cannot get node status from node due to network error, retrying...'"
                class="top-alert"
                v-if="apiContinuousErrorCount['node'] >= 3"
            ></a-alert>
            <a-alert
                type="error"
                :message="'Cannot get system info from node due to network error, retrying...'"
                class="top-alert"
                v-if="apiContinuousErrorCount['system'] >= 3"
            ></a-alert>
            <a-alert
                type="error"
                :message="'Cannot get task info from node due to network error, retrying...'"
                class="top-alert"
                v-if="apiContinuousErrorCount['task'] >= 3"
            ></a-alert>
            <a-alert
                type="error"
                :message="'Transaction error: ' + nodeStatus.tx_error + '. Please try again later.'"
                class="top-alert"
                v-if="nodeStatus.tx_status === nodeAPI.TX_STATUS_ERROR"
            ></a-alert>
            <a-alert
                message="Waiting for the Blockchain confirmation..."
                class="top-alert"
                v-if="nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
            ></a-alert>
            <a-alert
                message="Node will stop after finishing the current task"
                class="top-alert"
                v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_STOP"
            ></a-alert>
            <a-alert
                message="Node will pause after finishing the current task"
                class="top-alert"
                v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_PAUSE"
            ></a-alert>
            <a-alert
                type="error"
                message="Waiting for tokens. At least 400.01 test CNXs are required."
                class="top-alert"
                v-if="
          (nodeStatus.status === nodeAPI.NODE_STATUS_STOPPED || nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING) &&
          accountStatus.address !== '' &&
          !ethEnough()
        "
            >
                <template #action>
                    <a-button size="small" type="primary" :href="config.discord_link" target="_blank">Crynux Discord
                    </a-button>
                </template>
                <template #description>
                    Get the test CNXs for free:
                    <a-typography-link :href="config.discord_link" target="_blank">{{ config.discord_link }}
                    </a-typography-link>
                </template>
            </a-alert>
            <a-alert
                type="error"
                message="Waiting for tokens. At least 0.01 test CNXs are required for the gas fee."
                class="top-alert"
                v-if="
          nodeStatus.status !== nodeAPI.NODE_STATUS_STOPPED &&
          nodeStatus.status !== nodeAPI.NODE_STATUS_INITIALIZING &&
          accountStatus.address !== '' &&
          !ethEnoughForGas()
        "
            >
                <template #action>
                    <a-button size="small" type="primary" :href="config.discord_link" target="_blank">Crynux Discord
                    </a-button>
                </template>
                <template #description>
                    Get the test CNXs for free:
                    <a-typography-link :href="config.discord_link" target="_blank">{{ config.discord_link }}
                    </a-typography-link>
                </template>
            </a-alert>
        </a-col>
    </a-row>
    <a-row :gutter="[16, 16]">
        <a-col
            :xs="{ span: 24, offset: 0, order: 1 }"
            :sm="{ span: 12, offset: 0, order: 1 }"
            :md="{ span: 12, offset: 0, order: 1 }"
            :lg="{ span: 5, offset: 0, order: 1 }"
            :xl="{ span: 5, offset: 1, order: 1 }"
            :xxl="{ span: 4, offset: 3, order: 1 }"
        >
            <a-card title="Node Status" :bordered="false" style="height: 100%; opacity: 0.9">
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
                [
                  nodeAPI.NODE_STATUS_PENDING_PAUSE,
                  nodeAPI.NODE_STATUS_PENDING_STOP,
                  nodeAPI.NODE_STATUS_INITIALIZING
                ].indexOf(nodeStatus.status) !== -1
              "
                        >
                            <template #format="percent">
                <span style="font-size: 14px; color: cornflowerblue">
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_PAUSE"
                  >Pausing</span
                  >
                  <span v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_STOP"
                  >Stopping</span
                  >
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
                                :disabled="!ethEnough()"
                            >Pause
                            </a-button
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
                                :disabled="!ethEnough()"
                            >Stop
                            </a-button
                            >
                        </div>
                        <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_STOPPED">
                            <a-button
                                type="primary"
                                :icon="h(PlayCircleOutlined)"
                                @click="sendNodeAction('start')"
                                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                                :disabled="!ethEnough()"
                            >Start
                            </a-button
                            >
                        </div>
                        <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_PAUSED">
                            <a-button
                                type="primary"
                                :icon="h(PlayCircleOutlined)"
                                @click="sendNodeAction('resume')"
                                :loading="isTxSending || nodeStatus.tx_status === nodeAPI.TX_STATUS_PENDING"
                                :disabled="!ethEnough()"
                            >Resume
                            </a-button
                            >
                        </div>
                        <div class="node-op-btn" v-if="nodeStatus.status === nodeAPI.NODE_STATUS_INITIALIZING">
                            <a-button type="primary" :icon="h(PlayCircleOutlined)" disabled>Start</a-button>
                        </div>
                    </a-col>
                </a-row>
            </a-card>
        </a-col>

        <a-col
            :xs="{ span: 24, order: 3 }"
            :sm="{ span: 24, order: 3 }"
            :md="{ span: 24, order: 3 }"
            :lg="{ span: 12, order: 2 }"
            :xl="{ span: 11, order: 2 }"
            :xxl="{ span: 9, order: 2 }"
        >
            <a-card title="Wallet" :bordered="false" style="height: 100%; opacity: 0.9">
                <template #extra>
                    <edit-account
                        ref="accountEditor"
                        :account-status="accountStatus"
                        @private-key-updated="privateKeyUpdated"
                    ></edit-account>
                </template>
                <a-row>
                    <a-col :span="12">
                        <a-tooltip>
                            <template #title>{{ accountStatus.address }}</template>
                            <a-statistic title="Address" class="wallet-address">
                                <template #formatter>
                                    <span>{{ shortAddress }}</span>
                                    <a-button @click="copyText(accountStatus.address)">
                                        <template #icon>
                                            <CopyOutlined />
                                        </template>
                                    </a-button>
                                </template>
                            </a-statistic>
                        </a-tooltip>
                    </a-col>
                    <a-col :span="6">
                        <a-statistic title="Staked" class="wallet-value">
                            <template #formatter>
                                <a-typography-link
                                    v-if="nodeStatus.status === nodeAPI.NODE_STATUS_RUNNING || nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_PAUSE || nodeStatus.status === nodeAPI.NODE_STATUS_PENDING_STOP"
                                    :href="config.block_explorer + '/address/' + accountStatus.address"
                                    target="_blank">{{ toEtherValue(BigInt(400e18)) }}</a-typography-link>
                                <a-typography-text v-else>0</a-typography-text>
                            </template>
                        </a-statistic>
                    </a-col>
                    <a-col :span="6">
                        <a-statistic title="Balance (Test CNX)" class="wallet-value">
                            <template #formatter>
                                <a-typography-link
                                    v-if="accountStatus.address !== ''"
                                    :href="config.block_explorer + '/address/' + accountStatus.address"
                                    target="_blank">{{ toEtherValue(accountStatus.balance) }}</a-typography-link>
                                <a-typography-text v-else>0</a-typography-text>
                            </template>
                        </a-statistic>
                    </a-col>
                </a-row>
            </a-card>
        </a-col>

        <a-col
            :xs="{ span: 24, order: 2 }"
            :sm="{ span: 12, order: 2 }"
            :md="{ span: 12, order: 2 }"
            :lg="{ span: 7, order: 3 }"
            :xl="{ span: 6, order: 3 }"
            :xxl="{ span: 5, order: 3 }"
        >
            <a-card title="Task Execution" :bordered="false" style="height: 100%; opacity: 0.9">
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
                            status="success"
                            v-else-if="taskStatus.status === 'running'"
                        >
                            <template #format="percent">
                                <span style="font-size: 14px">Running</span>
                            </template>
                        </a-progress>

                        <a-progress
                            type="circle"
                            :size="70"
                            :percent="100"
                            :stroke-color="'lightgray'"
                            v-else
                        >
                            <template #format="percent">
                                <span style="font-size: 14px; color: lightgray">Stopped</span>
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
    <a-row :gutter="[16, 16]" style="margin-top: 16px">
        <a-col
            :xs="{ span: 24, offset: 0 }"
            :sm="{ span: 16, offset: 0 }"
            :md="{ span: 16, offset: 0 }"
            :lg="{ span: 9, offset: 0 }"
            :xl="{ span: 7, offset: 1 }"
            :xxl="{ span: 6, offset: 3 }"
        >
            <a-card title="GPU" :bordered="false" style="height: 100%; opacity: 0.9">
                <a-row>
                    <a-col :span="8">
                        <a-progress type="dashboard" :size="80" :percent="getPercent(systemInfo.gpu.usage)" />
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
                                    :value="systemInfo.gpu.vram_used_mb"
                                    :value-style="{ 'font-size': '14px' }"
                                >
                                    <template #title><span style="font-size: 12px">VRAM Used</span></template>
                                    <template #suffix>MB</template>
                                </a-statistic>
                            </a-col>
                            <a-col :span="12">
                                <a-statistic
                                    :value="systemInfo.gpu.vram_total_mb"
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
        <a-col :xs="12" :sm="8" :md="8" :lg="5" :xxl="4">
            <a-card title="CPU" :bordered="false" style="height: 100%; opacity: 0.9">
                <a-row>
                    <a-col :span="12">
                        <a-progress type="dashboard" :size="80" :percent="getPercent(systemInfo.cpu.usage)" />
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
                                    :value="systemInfo.cpu.frequency_mhz"
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
        <a-col :xs="12" :sm="12" :md="12" :lg="5" :xxl="4">
            <a-card title="Memory" :bordered="false" style="height: 100%; opacity: 0.9">
                <a-row>
                    <a-col :span="12">
                        <a-progress
                            type="dashboard"
                            :size="80"
                            :percent="
                getPercent(Math.round(
                  ((systemInfo.memory.total_mb - systemInfo.memory.available_mb) /
                    systemInfo.memory.total_mb) *
                    100
                ))
              "
                        />
                    </a-col>
                    <a-col :span="12">
                        <a-row>
                            <a-col :span="24">
                                <a-statistic
                                    :value="systemInfo.memory.total_mb - systemInfo.memory.available_mb"
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
                                    :value="systemInfo.memory.total_mb"
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
        <a-col :xs="12" :sm="12" :md="12" :lg="5" :xxl="4">
            <a-card title="Disk" :bordered="false" style="height: 100%; opacity: 0.9">
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
    <div id="bottom-bar" :class="{'bottom-bar': true, 'fixed-bottom-bar': fixedBottomBar}">
        <a-space class="footer-links" align="center" :direction="screens['xs'] ? 'vertical' : 'horizontal'">
            <a-typography-link href="https://crynux.ai" target="_blank">Home</a-typography-link>
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-link href="https://docs.crynux.ai" target="_blank">Docs</a-typography-link>
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-link href="https://blog.crynux.ai" target="_blank">Blog</a-typography-link>
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-link href="https://twitter.com/crynuxai" target="_blank"
            >Twitter
            </a-typography-link
            >
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-link :href="config.discord_link" target="_blank"
            >Discord
            </a-typography-link
            >
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-link href="https://netstats.crynux.ai" target="_blank"
            >Netstats
            </a-typography-link
            >
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <a-typography-text :style="{'color':'white'}">v{{ appVersion }}</a-typography-text>
            <span class="bottom-bar-divider">&nbsp;|&nbsp;</span>
            <!-- Place this tag where you want the button to render. -->
            <github-button
                href="https://github.com/crynux-ai/crynux-node"
                data-color-scheme="no-preference: light; light: light; dark: light;"
                data-show-count="true" aria-label="Star Crynux Node on GitHub"
                :style="{'position': 'relative', 'top': '4px'}"
            >Star
            </github-button>
        </a-space>
        <img class="footer-logo" src="./logo-full-white.png" width="140" alt="Crynux logo" />
    </div>
</template>

<style lang="stylus">
.ant-row
    margin-left 0 !important
    margin-right 0 !important
</style>
<style scoped lang="stylus">
.wallet-value a,
    .wallet-value span
    font-size 24px
    color black
    text-decoration none

.xs .wallet-value a,
.xs .wallet-value span,
.xs .wallet-address span
    font-size 16px

.wallet-value a:hover
    color #1677ff

.top-alert
    margin-bottom 16px

.fixed-bottom-bar.bottom-bar
    position fixed
    bottom 0
    left 0
    margin-top 0

.bottom-bar
    position relative
    width 100%
    height 60px
    padding 0 32px
    margin-top 68px

.xs .bottom-bar .bottom-bar-divider
    display none

.footer-links
    color #fff
    opacity 0.8
    line-height 60px

    a
        color #fff

        &:hover
            text-decoration underline

.xs .footer-links
    line-height 24px

.footer-logo
    opacity 0.8
    float right

.xs .top-row
    height 64px
.sm .top-row
    height 64px
.md .top-row
    height 64px
.lg .top-row
    height 64px
.xl .top-row
    height 80px
.xxl .top-row
    height 100px
</style>
