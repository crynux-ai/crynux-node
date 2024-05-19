import ApiError from './api-error'

class BaseApi {
    constructor() {
        this.ErrorType = ApiError.Type
        this.httpClient = null
    }

    setHttpClient(client) {
        this.httpClient = client
    }

    getHttpClient() {
        return this.httpClient
    }
}

export default BaseApi
