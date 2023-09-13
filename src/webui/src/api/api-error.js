class ApiError extends Error {
  constructor(type, data) {
    super(type + ': ' + JSON.stringify(data))
    this.type = type
    this.data = data
  }

  toString() {
    return this.type + ': ' + JSON.stringify(this.data)
  }
}

ApiError.Type = {
  Validation: 'Validation Error',
  Server: 'Internal Server Error',
  Forbidden: 'Forbidden Error',
  NotFound: 'Not Found',
  Unknown: 'Unknown Error'
}

export default ApiError
