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
  }

  getNodeStatus() {
    return v1.get('/node')
  }

  startNode() {
    return v1.post('/node', {
      action: 'start'
    })
  }

  stopNode() {
    return v1.post('/node', {
      action: 'stop'
    })
  }

  pauseNode() {
    return v1.post('/node', {
      action: 'pause'
    })
  }

  resumeNode() {
    return v1.post('/node', {
      action: 'resume'
    })
  }
}

const nodeAPI = new NodeAPI()

export default nodeAPI
