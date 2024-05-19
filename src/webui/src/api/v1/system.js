import BaseAPI from '../base-api'
import V1Client from '@/api/v1/v1'
import config from '@/config.json'

class SystemAPI extends BaseAPI {

    constructor() {
        super()
        this.setHttpClient(new V1Client(config.base_url))
    }

    getSystemInfo() {
        return this.getHttpClient().get('/system')
    }
}

export default SystemAPI
