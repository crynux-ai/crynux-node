import json
import time
import logging
from typing import Any, Dict, Optional, Tuple

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from crynux_server.utils import sort_dict


class Signer(object):
    def __init__(self, privkey: str) -> None:
        self.account: LocalAccount = Account.from_key(privkey)

    def sign(
        self, input: Dict[str, Any], timestamp: Optional[int] = None
    ) -> Tuple[int, str]:
        ordered_input = sort_dict(input)

        input_bytes = json.dumps(
            ordered_input, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if timestamp is None:
            timestamp = int(time.time())
        t_bytes = str(timestamp).encode("utf-8")

        data_hash = Web3.keccak(input_bytes + t_bytes)

        res = bytearray(self.account.signHash(data_hash).signature)
        res[-1] -= 27
        return timestamp, "0x" + res.hex()
