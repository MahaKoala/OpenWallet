from bitcoin.core.serialize import Hash160
from bitcoin.wallet import CBitcoinAddress, P2PKHBitcoinAddress, P2SHBitcoinAddress, P2WPKHBitcoinAddress
from bitcoin.core.script import OP_0, OP_CHECKSIG, OP_DUP, OP_EQUAL, OP_EQUALVERIFY, OP_HASH160
from typing import List, Set
from bitcoin import bitcoin
from bip32 import BIP32, HARDENED_INDEX
import hashlib
import logging
import esplora

'''

@seed: The seed as bytes.
@path: An example of path is m/44'/0'/0'/0/0.
'''
def bip32_derive_pubkey(seed: bytes, path: str) -> bytes:
   bip32 = BIP32.from_seed(seed)
   return bip32.get_pubkey_from_path(path)

class Address:
    def __init__(self, is_change, address, balance):
        self._is_change = is_change
        self._address: CBitcoinAddress = address
        self._balance = balance

class Wallet:
    def __init__(self):
        self._balance = 0
        self._addresses: List[Address] = []

class Bip44Path:
    # m / purpose' / coin_type' / account' / change / address_index
    def __init__(self, seed, purpose, coin_type):
        self._seed = seed
        self._purpose = purpose
        self._coin_type = coin_type
        
    def derive_pubkey(self, account, change, address_index) -> bytes:
        path = "m/{purpose}'/{coin_type}'/{account}'/{change}/{index}".format(
            purpose=self._purpose, coin_type=self._coin_type, account=account, change=change,
            index=address_index)
        pubkey: bytes = bip32_derive_pubkey(self._seed, path)
        return pubkey
        
'''
Given a seed and path, discover all its addresses. BIP 44 specifies addresses are sequentially increasing,
but it does not specify how. Here we assume for each account, addresses are sequentially increasing
respecting a gap limit .
'''
def bip84_discover_addresses(seed: bytes, num_of_accounts: int, is_change: bool,
                             bip84_path: Bip44Path, gap_limit: int) -> List[P2WPKHBitcoinAddress]:
    addrs: List[P2WPKHBitcoinAddress] = []
    for account_i in range(num_of_accounts):
        stop_at = gap_limit
        index = 0
        while index < stop_at:
            change = 1 if is_change else 0
            pubkey: bytes = bip84_path.derive_pubkey(account_i, change, index)
            p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
            p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)
            if esplora.existaddress(p2wpkh_addr):
                stop_at = index + gap_limit + 1
            addrs.append(p2wpkh_addr)
            index += 1

    return addrs


def discover_bip84_wallet(seed: bytes, gap_limit=20) -> Wallet:
    bip84_path = Bip44Path(seed, 84, 0)

     # discovering accounts according to "Account discovery" in BIP 44.
    num_of_accounts = 0
    index = 0
    while index < gap_limit:
        pubkey: bytes = bip84_path.derive_pubkey(num_of_accounts, 0, index)
        p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
        p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)
        if esplora.existaddress(p2wpkh_addr):
            index = 0
            num_of_accounts += 1
        else:
            index += 1

    logging.debug("There are %d of account." % (num_of_accounts, ))

    # Discovery addresses.
    receiving_addrs = bip84_discover_addresses(
        seed, num_of_accounts, False, bip84_path, gap_limit)
    change_addrs = bip84_discover_addresses(
       seed, num_of_accounts, True, bip84_path, gap_limit)
    all_addresses = receiving_addrs + change_addrs

    logging.debug("There are %d addresses." % (len(all_addresses),))

    # Populate Wallet.
    addr_url = "https://blockstream.info/api/address/{addr}"
    wallet = Wallet()
    for addr in receiving_addrs:
        address_resopnse = esplora.address(addr)
        wallet._balance += address_resopnse._balance
        wallet._addresses.append(
            Address(False, addr, address_resopnse._balance))

    for addr in change_addrs:
        address_resopnse = esplora.address(addr)
        wallet._balance += address_resopnse._balance
        wallet._addresses.append(
            Address(True, addr, address_resopnse._balance))

    return wallet
