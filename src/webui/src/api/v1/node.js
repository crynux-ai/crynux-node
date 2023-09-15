import BaseAPI from '../base-api'
import v1 from './v1'

class NodeAPI extends BaseAPI {
  constructor() {
    super()

    this.NODE_STATUS_INITIALIZING = 'initializing'
    this.NODE_STATUS_RUNNING = 'running'
    this.NODE_STATUS_PAUSED = 'paused'
    this.NODE_STATUS_STOPPED = 'stopped'
    this.NODE_STATUS_ERROR = 'error'
    this.NODE_STATUS_PENDING = 'pending'

    this.TX_STATUS_ERROR = 'error'
    this.TX_STATUS_PENDING = 'pending'
    this.TX_STATUS_NONE = ''
  }

  getNodeStatus() {
    return v1.get('/node')
  }

  sendNodeAction(action) {
    return v1.post('/node', {
      action: action
    })
  }
}

const nodeAPI = new NodeAPI()

export default nodeAPI
