import BaseAPI from '../base-api'
import v1 from './v1'

class TaskAPI extends BaseAPI {
  getTaskRunningStatus() {
    return v1.get('/tasks')
  }
}

const taskAPI = new TaskAPI()

export default taskAPI
