from bitcoin.core.serialize import Hash160
from bitcoin.wallet import CBitcoinAddress, P2PKHBitcoinAddress, P2SHBitcoinAddress, P2WPKHBitcoinAddress
from bitcoin.core.script import OP_0, OP_CHECKSIG, OP_DUP, OP_EQUAL, OP_EQUALVERIFY, OP_HASH160
from typing import List, Set
from bitcoin import bitcoin
from bip32 import BIP32, HARDENED_INDEX
import hashlib
import logging
import esplora
from wallet import Wallet, Bip44Path, Address
    
'''
Given a seed and path, discover all its addresses. BIP 44 specifies addresses are sequentially increasing,
but it does not specify how. Here we assume for each account, addresses are sequentially increasing
respecting a gap limit.
'''
def bip84_discover_addresses(seed: bytes, num_of_accounts: int, is_change: bool,
                             bip84_path: Bip44Path, gap_limit: int) -> List[Address]:
    addrs: List[(P2WPKHBitcoinAddress, int)] = []
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
            addrs.append(Address(is_change, index, account_i, p2wpkh_addr, 0))
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

    # Populate addresses in the Wallet.
    wallet = Wallet(seed)
    wallet.balance = 0
    receiving_address_responses = esplora.addresses(
        [address.address for address in receiving_addrs])
    for i, address_resopnse in enumerate(receiving_address_responses):
        wallet.balance += address_resopnse.balance
        receiving_addrs[i].balance = address_resopnse.balance
        wallet.receive_addresses.append(receiving_addrs[i])

    change_address_responses = esplora.addresses(
        [address.address for address in change_addrs])
    for i, address_resopnse in enumerate(change_address_responses):
        wallet.balance += address_resopnse.balance
        change_addrs[i].balance = address_resopnse.balance
        wallet.change_addresses.append(change_addrs[i])

    return wallet
