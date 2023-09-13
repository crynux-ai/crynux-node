import BaseAPI from '../base-api'
import v1 from './v1'

class SystemAPI extends BaseAPI {
  getSystemInfo() {
    return v1.get('/system')
  }
}

const systemAPI = new SystemAPI()

export default systemAPI
