import BaseAPI from '../base-api'
import V1Client from '@/api/v1/v1'
import config from '@/config.json'

class TaskAPI extends BaseAPI {

    constructor() {
        super()
        this.setHttpClient(new V1Client(config.base_url))
    }

    getTaskRunningStatus() {
        return this.getHttpClient().get('/tasks')
    }
}

export default TaskAPI
