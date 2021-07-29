from bitcoin.core.serialize import Hash160
from bitcoin.wallet import CBitcoinAddress, P2PKHBitcoinAddress, P2SHBitcoinAddress, P2WPKHBitcoinAddress
from bitcoin.core import COutPoint, CTransaction
from bitcoin.core.script import OP_0, OP_CHECKSIG, OP_DUP, OP_EQUAL, OP_EQUALVERIFY, OP_HASH160
from typing import List, Set
from bitcoin import bitcoin
from bip32 import BIP32, HARDENED_INDEX
import hashlib
import logging
import discovery
import time
from config import Config

'''

@seed: The seed as bytes.
@path: An example of path is m/44'/0'/0'/0/0.
'''

COIN = 100000000

def bip32_derive_pubkey(seed: bytes, path: str) -> bytes:
   bip32 = BIP32.from_seed(seed)
   return bip32.get_pubkey_from_path(path)


class Address:
    def __init__(self, is_change, address_index, account_no, address, balance):
        self.is_change = is_change
        self.address_index = address_index
        self.address: CBitcoinAddress = address
        self.account_no = account_no
        self.balance = balance

class UnspentOutput:
    '''
    @amount in satoshi
    '''
    def __init__(self, outpoint: COutPoint, amount: int):
        pass


class Bip44Path:
    # m / purpose' / coin_type' / account' / change / address_index
    def __init__(self, seed, purpose, coin_type):
        self._seed = seed
        self._purpose = purpose
        self._coin_type = coin_type

    def derive_pubkey(self, account, change: int, address_index) -> bytes:
        path = "m/{purpose}'/{coin_type}'/{account}'/{change}/{index}".format(
            purpose=self._purpose, coin_type=self._coin_type, account=account, change=change,
            index=address_index)
        pubkey: bytes = bip32_derive_pubkey(self._seed, path)
        return pubkey


class Wallet:
    def __init__(self, seed):
        '''
        Is Bitcoin Bech 32 P2WPKH wallet 
        '''
        self._bip84_path = Bip44Path(seed, 84, 0)
        self._seed = seed
        self.balance = 0
        self.new_addresses: List[Address] = []
        self.receive_addresses: List[Address] = []
        self.change_addresses: List[Address] = []

        self.last_sync = time.time()

    def new_address(self) -> CBitcoinAddress:
        # Find the last used index of account 0.
        last_used_index = -1
        for receive_address in self.receive_addresses + self.new_addresses:
            if receive_address.account_no == 0 and receive_address.address_index > last_used_index:
                last_used_index = receive_address.address_index
        
        next_index = last_used_index + 1

        pubkey: bytes = self._bip84_path.derive_pubkey(0, 0, next_index)
        p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
        p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)

        self.new_addresses.append(Address(False, next_index, 0, p2wpkh_addr, 0))
        return p2wpkh_addr

    def sync(self):
        bip84_wallet = discovery.discover_bip84_wallet(self._seed, Config.GapLimit)
        self.balance = bip84_wallet.balance
        self.receive_addresses: List[Address] = bip84_wallet.receive_addresses
        self.change_addresses: List[Address] = bip84_wallet.change_addresses

        # Remove new addresses if it is found in self._receive_addresses. In other words,
        # remove new addresses that has received some bitcoin.
        self.new_addresses = list(filter(
            lambda addr: addr not in self.receive_addresses, self.new_addresses))
    
    def request_sync(self):
        # sync is honored if last time sync is more than 30 seconds ago.
        threshold = 30
        if time.time() - self.last_sync > threshold:
            self.sync()
            self.last_sync = time.time()

    def send(target: CBitcoinAddress):
        pass

