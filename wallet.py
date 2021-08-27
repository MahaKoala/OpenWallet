from bitcoin.core.serialize import Hash160
from bitcoin.wallet import CBitcoinAddress, P2PKHBitcoinAddress, P2SHBitcoinAddress, P2WPKHBitcoinAddress, CKey
from bitcoin.core import COutPoint, CTransaction, lx, CTxIn, CTxOut, CMutableTransaction, CTxInWitness, CScriptWitness, CTxWitness
from bitcoin.core.script import OP_0, OP_CHECKSIG, OP_DUP, OP_EQUAL, OP_EQUALVERIFY, OP_HASH160, CScript, SignatureHash, SIGHASH_ALL, SIGVERSION_WITNESS_V0
from typing import List, Set
from bitcoin import bitcoin
from bip32 import BIP32, HARDENED_INDEX
import hashlib
import binascii
import logging
import discovery
import time
import esplora
import fullnode
import math
from config import Config

'''

@seed: The seed as bytes.
@path: An example of path is m/44'/0'/0'/0/0.
'''

COIN = 100000000

def bip32_derive_pubkey(seed: bytes, path: str) -> bytes:
   bip32 = BIP32.from_seed(seed)
   return bip32.get_pubkey_from_path(path)

def bip32_derive_privkey(seed: bytes, path: str) -> bytes:
    bip32 = BIP32.from_seed(seed)
    return bip32.get_privkey_from_path(path)

class Address:
    def __init__(self, is_change, address_index, account_no, address, balance):
        self.is_change = is_change
        self.address_index = address_index
        self.address: CBitcoinAddress = address
        self.account_no = account_no
        self.balance = balance

class UnspentOutput:
    def __init__(self, txid: str, vout: int, value, address):
        self.txid = txid
        self.vout = vout
        self.value = value
        self.address: CBitcoinAddress = address
        # True if a TX has been broadcasted successfully with this utxo as input.
        self.sent = False

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
    
    def derive_private_key(self, account, change: int, address_index) -> bytes:
        path = "m/{purpose}'/{coin_type}'/{account}'/{change}/{index}".format(
            purpose=self._purpose, coin_type=self._coin_type, account=account, change=change,
            index=address_index)
        privkey: bytes = bip32_derive_privkey(self._seed, path)
        return privkey

class Wallet:
    def __init__(self, seed):
        '''
        Is Bitcoin Bech 32 P2WPKH wallet 
        '''
        self.path_prefix = "m/84'/0'"
        self._bip84_path = Bip44Path(seed, 84, 0)
        self._seed = seed
        self.balance = 0
        self.new_addresses: List[Address] = []
        self.receive_addresses: List[Address] = []
        self.new_change_addresses: List[Address] = []
        self.change_addresses: List[Address] = []
        self.unspent_outputs: List[UnspentOutput] = []

        self.last_sync = time.time()

    def new_address(self, change=False) -> CBitcoinAddress:
        addresses = self.receive_addresses if not change else self.change_addresses
        new_addresses = self.new_addresses if not change else self.new_change_addresses
        change_index = 0 if not change else 1

        # Find the last used address index of account 0.
        last_used_address_index = -1
        for address in addresses:
            if address.account_no == 0 and address.address_index > last_used_address_index:
                last_used_address_index = address.address_index

        new_address_index = last_used_address_index+1
        for address in new_addresses:
            if address.account_no == 0 and address.address_index >= new_address_index:
                new_address_index = address.address_index + 1
                if new_address_index - last_used_address_index + 1 > Config.GapLimit:
                    # the new (unused) address has to be within gap limit, otherwise the address is un-discoverable.
                    raise Exception("Attempt to generate a address that is out of the range (Gap Limit). Abort.")
                
        logging.debug("The index of the new address is " + \
                      str(new_address_index))
        pubkey: bytes = self._bip84_path.derive_pubkey(
            0, change_index, new_address_index)
        p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
        p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)

        new_addresses.append(
            Address(change, new_address_index, 0, p2wpkh_addr, 0))
        return p2wpkh_addr

    def _find_seckey(self, bitcoin_address: CBitcoinAddress) -> CKey:
        for address in self.change_addresses + self.receive_addresses:
            if str(address.address) == str(bitcoin_address):
                change = 1 if address.is_change else 0
                privkey: bytes = self._bip84_path.derive_private_key(
                    address.account_no, change, address.address_index)
                return CKey(privkey)
                # privkey_based58 = bitcoin.base58.encode(privkey)
                # logging.debug("privkey_based58: {} and {}".format(
                #     type(privkey_based58), privkey_based58))
                # seckey: CBitcoinSecret = CBitcoinSecret(privkey_based58)
        return None

    def sync(self):
        bip84_wallet = discovery.discover_bip84_wallet(self._seed, Config.GapLimit)
        self.balance = bip84_wallet.balance
        self.receive_addresses: List[Address] = bip84_wallet.receive_addresses
        self.change_addresses: List[Address] = bip84_wallet.change_addresses

        # Remove new addresses if it is found in self._receive_addresses. In other words,
        # remove new addresses that has received some bitcoin.
        self.new_addresses = list(filter(
            lambda addr: addr not in self.receive_addresses, self.new_addresses))
        self.new_change_addresses = list(filter(
            lambda addr: addr not in self.change_addresses, self.new_change_addresses))

        # Search for UTXOs.
        total_spendable_addresses: List[CBitcoinAddress] = []
        for address in self.receive_addresses + self.change_addresses:
            total_spendable_addresses.append(address.address)
        utxos: Dict[str, Set[UnspentOutput]] = esplora.utxos(
            total_spendable_addresses)

        self.unspent_outputs = []
        for unspent_output_set in utxos.values():
            for unspent_output in unspent_output_set:
                self.unspent_outputs.append(unspent_output)
    
    def request_sync(self):
        # sync is honored if last time sync is more than 30 seconds ago.
        threshold = 30
        if time.time() - self.last_sync > threshold:
            start = time.time()
            self.sync()
            interal = int((time.time() - start)*1000)
            logging.info("Sync took {} ms.".format(interal))
            self.last_sync = time.time()
    
    def _find_unspent_output(self, txid: str, vout: int) -> UnspentOutput:
        for utxo in self.unspent_outputs:
            if utxo.txid == txid and utxo.vout == vout:
                return utxo
        return None

    def _signrawtransactionwithkey(self):
        pass
    
    def send(self, value: int, utxos: List[UnspentOutput], destination: CBitcoinAddress, fee=0):
        available_fund = 0
        for i in range(len(utxos)):
            found: UnspentOutput = self._find_unspent_output(
                utxos[i].txid, utxos[i].vout)
            assert found is not None
            assert not isinstance(
                utxos[i].address, P2WPKHBitcoinAddress), "Only suppprot P2WPKH UTXOs."

            # copy over fields
            utxos[i].value = found.value
            utxos[i].address = found.address
            available_fund += found.value

        if fee == 0:
            # calculate vbytes according to https://bitcoinops.org/en/tools/calc-size/
            # Assumption which is valid for this Wallet:
            # 1) input count is no geater than 252.
            # 2) inputs are all P2WPKH
            overhead_vbytes = 10.5
            input_vbtyes = 68.25 * len(utxos)
            output_vbytes = 0
            if isinstance(destination, P2WPKHBitcoinAddress):
                output_vbytes += 31
            elif isinstance(destination, P2PKHBitcoinAddress) or isinstance(destination, P2SHBitcoinAddress):
                output_vbytes += 8 + 2 + len(destination.to_scriptPubKey())
            else:
                raise "Unsupported address type: " + str(type(destination))
            # Assume there is always a change address.
            output_vbytes += 31

            sats_per_vbyte = esplora.fee_estimates(1)
            fee = math.ceil(sats_per_vbyte * (overhead_vbytes+input_vbtyes+output_vbytes))  

        assert available_fund >= fee + value, "Insufficient fund for sending"
        
        # The code for creating a signed transacation is based off 
        # https://github.com/petertodd/python-bitcoinlib/blob/python-bitcoinlib-v0.11.0/examples/spend-p2wpkh.py 

        txins = []
        for utxo in utxos:
            nSequence = 0xffffffff
            if Config.EnableBip125Rfb:
                # Explicit signaling: A transaction is considered to have opted in to allowing replacement of itself
                # if any of its inputs have an nSequence number less than (0xffffffff - 1).
                # Code: https://github.com/bitcoin/bitcoin/blob/v0.21.2rc1/src/validation.cpp#L610-L635
                # BIP 125: https://github.com/bitcoin/bips/blob/master/bip-0125.mediawiki
                nSequence = 0xfffffffd
            txin = CTxIn(COutPoint(lx(utxo.txid), utxo.vout),
                         nSequence=nSequence)
            txins.append(txin)
        
        # Spend to the destination.
        txouts = []
        txouts.append(CTxOut(value, destination.to_scriptPubKey()))
        if (available_fund - fee - value > 0):
            # Rest of the fund goes to change address.
            chnage_address: CBitcoinAddress = self.new_address(change=True)
            txouts.append(CTxOut(available_fund - fee - value, chnage_address.to_scriptPubKey()))
                    
        tx = CMutableTransaction(txins, txouts)

        logging.debug("Unsigned transaction: " + str(binascii.hexlify(tx.serialize())))

        # Signing
        witnesses = []
        for txin_index, txin in enumerate(txins):
            # Get SignatureHash (Transaction digest) for signing according to https://github.com/bitcoin/bips/blob/master/bip-0143.mediawiki#Native_P2WPKH
            utxo = utxos[txin_index]
            p2wpkh_bitcoin_address: P2WPKHBitcoinAddress = utxo.address
            sighash = SignatureHash(p2wpkh_bitcoin_address.to_redeemScript(), tx, txin_index, SIGHASH_ALL,
                                    amount=utxo.value, sigversion=SIGVERSION_WITNESS_V0)

            seckey: CKey = self._find_seckey(p2wpkh_bitcoin_address)
            assert seckey is not None, "Can't find privkey associated with the address"
            signature = seckey.sign(sighash) + bytes([SIGHASH_ALL])
            witness = [signature, seckey.pub]
            witnesses.append(witness)

        # Aggregate all of the witnesses together, and then assign them to the
        # transaction object.
        ctxinwitnesses = [CTxInWitness(CScriptWitness(witness)) for witness in witnesses]
        tx.wit = CTxWitness(ctxinwitnesses)

        logging.debug("Signed transaction: " +
                      str(binascii.hexlify(tx.serialize())))

        txid = fullnode.sendrawtransaction(tx.serialize())
        logging.debug("TXID: {}".format(txid))
        assert txid != "", "Failed to send tx"

        # Mark utxos as sent
        for txin_index, txin in enumerate(txins):
            utxo = utxos[txin_index]
            utxo = self._find_unspent_output(utxo.txid, utxo.vout)
            utxo.sent = True
        return (txid, fee)
