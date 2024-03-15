import BaseAPI from '../base-api'
import v1 from './v1'

class AccountAPI extends BaseAPI {
  getAccountInfo() {
    return v1.get('/account')
  }

  updatePrivateKey(privateKey) {
    return v1.put('/account', {
      type: 'private_key',
      private_key: privateKey
    })
  }

  updateKeystore(keystore, passphrase) {
    return v1.put('/account', {
      type: 'keystore',
      keystore: keystore,
      passphrase: passphrase
    })
  }

  createAccount() {
    return v1.post('/account', {})
  }
}

const accountAPI = new AccountAPI()

export default accountAPI
