<script setup>
import { h } from 'vue'
import { PauseCircleOutlined, LogoutOutlined } from '@ant-design/icons-vue'
import EditAccount from './edit-account.vue'
</script>

<template>
  <a-row style="height: 140px"></a-row>
  <a-row :gutter="16">
    <a-col :span="4" :offset="3">
      <a-card title="Node Status" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="12">
            <a-progress type="circle" :size="70" :percent="100" />
          </a-col>
          <a-col :span="12">
            <div class="node-op-btn">
              <a-button :icon="h(PauseCircleOutlined)">Pause</a-button>
            </div>
            <div class="node-op-btn" style="margin-top: 8px">
              <a-button :icon="h(LogoutOutlined)">Quit</a-button>
            </div>
          </a-col>
        </a-row>
      </a-card>
    </a-col>

    <a-col :span="8">
      <a-card title="Account" :bordered="false" style="height: 100%">
        <template #extra>
          <edit-account></edit-account>
        </template>
        <a-row>
          <a-col :span="12">
            <a-statistic title="Address" :value="'0xA1d5e...27cFE'"></a-statistic>
          </a-col>
          <a-col :span="6">
            <a-statistic title="ETH" :precision="2" :value="242"></a-statistic>
          </a-col>
          <a-col :span="6">
            <a-statistic title="CNX" :precision="2" :value="766"></a-statistic>
          </a-col>
        </a-row>
      </a-card>
    </a-col>

    <a-col :span="6">
      <a-card title="Task Execution" :bordered="false" style="height: 100%">
        <a-row>
          <a-col :span="8">
            <a-progress type="circle" :size="70" :percent="100" :stroke-color="'cornflowerblue'">
              <template #format="percent">
                <span style="font-size: 14px; color: cornflowerblue">Idle</span>
              </template>
            </a-progress>
          </a-col>
          <a-col :span="8">
            <a-statistic title="Today" :precision="0" :value="144"></a-statistic>
          </a-col>
          <a-col :span="8">
            <a-statistic title="Total" :precision="0" :value="2769"></a-statistic>
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
            <a-progress type="circle" :size="70" :percent="90" />
          </a-col>
          <a-col :span="16">
            <a-row>
              <a-col :span="24">
                <a-statistic
                  value="ROG Strix RTX4090 O24 Gaming"
                  :value-style="{ 'font-size': '14px' }"
                >
                  <template #title><span style="font-size: 12px">Card Model</span></template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="12">
                <a-statistic :value="14" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">VRAM Used</span></template>
                  <template #suffix>GB</template>
                </a-statistic>
              </a-col>
              <a-col :span="12">
                <a-statistic :value="24" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">VRAM Total</span></template>
                  <template #suffix>GB</template>
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
            <a-progress type="circle" :size="70" :percent="60" />
          </a-col>
          <a-col :span="12">
            <a-row>
              <a-col :span="24">
                <a-statistic value="16" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">Num of Cores</span></template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="24">
                <a-statistic value="5800" :value-style="{ 'font-size': '14px' }">
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
            <a-progress type="circle" :size="70" :percent="87" />
          </a-col>
          <a-col :span="12">
            <a-row>
              <a-col :span="24">
                <a-statistic value="2418" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">Memory Avail</span></template>
                  <template #suffix>MB</template>
                </a-statistic>
              </a-col>
            </a-row>
            <a-row style="margin-top: 12px">
              <a-col :span="24">
                <a-statistic value="13252" :value-style="{ 'font-size': '14px' }">
                  <template #title><span style="font-size: 12px">Memory Total</span></template>
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
        <template #extra><a href="javascript:void(0)">Clear</a></template>
        <a-row>
          <a-col :span="12">
            <a-statistic :value="14" :value-style="{ 'font-size': '14px' }">
              <template #title><span style="font-size: 12px">Base Models</span></template>
              <template #suffix>GB</template>
            </a-statistic>
          </a-col>
          <a-col :span="12">
            <a-statistic :value="24" :value-style="{ 'font-size': '14px' }">
              <template #title><span style="font-size: 12px">Lora Models</span></template>
              <template #suffix>GB</template>
            </a-statistic>
          </a-col>
        </a-row>
        <a-row style="margin-top: 12px">
          <a-col :span="12">
            <a-statistic :value="14" :value-style="{ 'font-size': '14px' }">
              <template #title><span style="font-size: 12px">Logs</span></template>
              <template #suffix>MB</template>
            </a-statistic>
          </a-col>
          <a-col :span="12">
            <a-statistic :value="7" :value-style="{ 'font-size': '14px' }">
              <template #title><span style="font-size: 12px">System</span></template>
              <template #suffix>GB</template>
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
