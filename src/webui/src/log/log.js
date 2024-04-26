import config from '../config.json'
import log from 'loglevel'

log.setLevel(config['log']['level'])

export default log
