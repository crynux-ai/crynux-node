from typing import Annotated, Any

from eth_typing import ChecksumAddress
from pydantic import BeforeValidator
from web3 import Web3
from web3.types import Wei


def bytes_from_hex(value: Any) -> Any:
    assert isinstance(value, str) and value.startswith("0x")
    return bytes.fromhex(value[2:])


def wei_from_str(value: Any) -> Any:
    assert isinstance(value, str)
    return Web3.to_wei(value, "wei")


def checksumaddress_from_str(value: Any) -> Any:
    assert isinstance(value, str)
    return Web3.to_checksum_address(value)


BytesFromHex = Annotated[bytes, BeforeValidator(bytes_from_hex)]
WeiFromStr = Annotated[Wei, BeforeValidator(wei_from_str)]
AddressFromStr = Annotated[ChecksumAddress, BeforeValidator(checksumaddress_from_str)]
