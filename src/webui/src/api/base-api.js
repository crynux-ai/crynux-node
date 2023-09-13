import ApiError from './api-error'

class BaseApi {
  constructor() {
    this.ErrorType = ApiError.Type
  }
}

export default BaseApi
