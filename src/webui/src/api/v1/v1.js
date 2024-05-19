import axios from 'axios'
import ApiError from '../api-error'
import jsonBig from 'json-bigint'

const jsonBigNative = jsonBig({
  useNativeBigInt: true
})


const V1ClientPrototype = {
    apiForbiddenErrorHandler: () => {
        console.error("request forbidden")
    },
    apiServerErrorHandler: (msg) => {
        console.error(msg)
    },
    apiUnknownErrorHandler: () => {
        console.error("request unknown error")
    }
}

class V1Client {
  constructor(baseUrl) {
    if (baseUrl === '') {
      baseUrl = window.location.protocol + '//' + window.location.host + '/manager'
    }

    this.baseURL = baseUrl
    this.v1BaseURL = baseUrl + '/v1'

    this.httpClient = axios.create({
      baseURL: this.v1BaseURL,
      timeout: 15000,
      transformResponse: [
        (data) => {
          if (!data) {
            return {}
          }

          return jsonBigNative.parse(data)
        }
      ],
      transformRequest: [
        (data, headers) => {
          headers['Content-Type'] = 'application/json'
          return jsonBigNative.stringify(data)
        }
      ]
    })

    this.httpClient.interceptors.response.use(
      (response) => {
        if (response.status === 200) {
          // Normal response
          return Promise.resolve(response.data)
        } else {
          return Promise.reject(new ApiError(ApiError.Type.Unknown))
        }
      },
      (error) => {
        if (error.response && error.response.status) {
          return this.processErrorStatus(error.response.status, error.response.data)
        } else {
          if (typeof this.apiUnknownErrorHandler === 'function') {
            let handler = this.apiUnknownErrorHandler
            handler()
          }
          return Promise.reject(new ApiError(ApiError.Type.Unknown))
        }
      }
    )
  }

  getBaseURL() {
    return this.baseURL
  }

  getV1BaseURL() {
    return this.v1BaseURL
  }

  post(url, data, config) {
    return this.httpClient.post(url, data, config)
  }

  put(url, data, config) {
    return this.httpClient.put(url, data, config)
  }

  get(url, config) {
    return this.httpClient.get(url, config)
  }

  delete(url, config) {
    return this.httpClient.delete(url, config)
  }

  processErrorStatus(status, errorData) {
    if (status === 400) {
      return Promise.reject(new ApiError(ApiError.Type.Validation, errorData.detail))
    } else if (status === 422) {
      return Promise.reject(new ApiError(ApiError.Type.Validation, errorData.detail[0].msg))
    } else if (status === 403) {
      if (typeof this.apiForbiddenErrorHandler === 'function') {
        let handler = this.apiForbiddenErrorHandler
        handler()
      }

      return Promise.reject(new ApiError(ApiError.Type.Forbidden))
    } else if (status === 404) {
      return Promise.reject(new ApiError(ApiError.Type.NotFound))
    } else if (status === 500) {
      if (typeof this.apiServerErrorHandler === 'function') {
        let handler = this.apiServerErrorHandler
        handler(errorData.detail)
      }

      return Promise.reject(new ApiError(ApiError.Type.Server))
    } else {
      if (typeof this.apiUnknownErrorHandler === 'function') {
        let handler = this.apiUnknownErrorHandler
        handler()
      }

      return Promise.reject(new ApiError(ApiError.Type.Unknown))
    }
  }
}

Object.setPrototypeOf(V1Client, V1ClientPrototype)

export default V1Client
