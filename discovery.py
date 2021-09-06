from bitcoin.core.serialize import Hash160
from bitcoin.wallet import CBitcoinAddress, P2PKHBitcoinAddress, P2SHBitcoinAddress, P2WPKHBitcoinAddress
from bitcoin.core.script import OP_0, OP_CHECKSIG, OP_DUP, OP_EQUAL, OP_EQUALVERIFY, OP_HASH160
from typing import List, Set, Tuple
from bitcoin import bitcoin
from bip32 import BIP32, HARDENED_INDEX
import hashlib
import logging
import esplora
import time
from wallet import Wallet, Bip44Path, Address
    
'''
Given a seed and path, discover all its addresses. BIP 44 specifies addresses are sequentially increasing,
but it does not specify how. Here we assume for each account, addresses are sequentially increasing
respecting a gap limit.
'''
def bip84_discover_addresses(seed: bytes, account_i: int, is_change: bool,
                             bip84_path: Bip44Path, gap_limit: int) -> Tuple[List[Address], int]:
    addrs: List[(P2WPKHBitcoinAddress, int)] = []
     
    stop_at = gap_limit
    index = 0
    last_exist_index = -1
    while index < stop_at:
        change = 1 if is_change else 0
        pubkey: bytes = bip84_path.derive_pubkey(account_i, change, index)
        p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
        p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)
        if esplora.existaddress(p2wpkh_addr):
            stop_at = index + gap_limit + 1
            last_exist_index = index
            addrs.append(Address(is_change, index, account_i, p2wpkh_addr, 0))
        else:
            addrs.append(Address(is_change, index,
                             account_i, p2wpkh_addr, 0))
        index += 1

    return addrs, last_exist_index

class DiscoverWalletResult():
    def __init__(self, receive_addresses: List[List[Address]],
                last_receive_address_index: List[int],
                change_addresses: List[List[Address]],
                last_change_address_index: List[int]):
        self.receive_addresses = receive_addresses
        self.last_receive_address_index = last_receive_address_index
        self.change_addresses = change_addresses
        self.last_change_address_index = last_change_address_index

def discover_bip84_wallet(seed: bytes, gap_limit=20) -> DiscoverWalletResult:
    bip84_path = Bip44Path(seed, 84, 0)

    # Discovery addresses.
    start = time.time()
    receive_addresses: List[List[Address]] = []
    last_receive_address_index: List[int] = []
    change_addresses: List[List[Address]] = []
    last_change_address_index: List[int] = []

    account_i = 0
    total_address_count = 0
    done = False
    while not done:
        receiving_addrs, index = bip84_discover_addresses(
            seed, account_i, False, bip84_path, gap_limit)
        if index == -1:
            done = True
            break
        
        receive_addresses.append(receiving_addrs)
        last_receive_address_index.append(index)

        change_addrs, index = bip84_discover_addresses(
            seed, account_i, True, bip84_path, gap_limit)
        change_addresses.append(change_addrs)
        last_change_address_index.append(index) # index could be -1

        account_i += 1
        total_address_count += len(change_addrs) + len(receiving_addrs)

    logging.debug("Discovered %d accounts and %d addresses, and it took %d ms." % (
        account_i, total_address_count, int((time.time() - start)*1000)))

    return DiscoverWalletResult(receive_addresses, last_receive_address_index,
        change_addresses, last_change_address_index)
