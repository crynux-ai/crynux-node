import secrets
from typing import List, Tuple

from web3 import Web3


def make_result_commitments(result_hashes: List[str]) -> Tuple[bytes, bytes, bytes]:
    result_bytes = [bytes.fromhex(h[2:]) for h in result_hashes]
    bs = b"".join(result_bytes)
    nonce = secrets.token_bytes(32)
    commitment = Web3.solidity_keccak(["bytes", "bytes32"], [bs, nonce])
    return bs, commitment, nonce
