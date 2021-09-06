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
from concurrent.futures import as_completed
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
        self.is_change: bool = is_change
        self.address_index = address_index
        self.address: CBitcoinAddress = address
        self.account_no = account_no
        self.balance = balance
        self.last_seen_txid = None

    # def empty(self):
    #     return self.last_seen_txid is None

class UnspentOutput:
    def __init__(self, txid: str, vout: int, value, address):
        self.txid = txid
        self.vout = vout
        self.value = value
        self.address: CBitcoinAddress = address
        # True if a TX has been broadcasted successfully with this utxo as input.
        self.sent = False
        self.spent = False

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

        # account no -> index -> Address
        self.receive_addresses: List[List[Address]] = []
        # account no -> index
        self.last_receive_address_index: List[int] = []

        self.change_addresses: List[List[Address]] = []
        self.last_change_address_index: List[int] = []

        # Key is bitcoin address 
        self.addresses_map: Map[str, Address] = {}
        # Key is txid:n, 
        self.unspent_outputs_map: Map[str, UnspentOutput] = {}
        self.last_sync = 0

        self.last_sync = time.time()
        self.syncing = False
    
    def get_new_change_address(self) -> CBitcoinAddress:
        account_0_change_addresses= self.change_addresses[0]
        account_0_last_index = self.last_change_address_index[0]
        assert account_0_last_index+1 < len(account_0_change_addresses), "No unused change addresses that are reserved?"
        return account_0_change_addresses[account_0_last_index+1].address

    def _find_seckey(self, bitcoin_address: CBitcoinAddress) -> CKey:
        address = self.addresses_map.get(str(bitcoin_address))
        if address is None:
            return None
        
        change = 1 if address.is_change else 0
        privkey: bytes = self._bip84_path.derive_private_key(
            address.account_no, change, address.address_index)
        return CKey(privkey)


    def sync_addresses(self):
        """
        Fast update based on GET /address/:address/txs and GET /address/:address/txs/chain[/:last_seen_txid]

        each address will keep track of what is the last txid that has sync up to, so that only txid after it are
        applied to UTXOs and the address balance.
        """
        if self.syncing:
            return
        self.syncing = True

        futures = []
        for account_i in range(len(self.receive_addresses)):
            cur_receive_addresses = self.receive_addresses[account_i]
            for index in range(0, len(cur_receive_addresses)):
                cur_receive_address = cur_receive_addresses[index]
                future = esplora.gThreadPoolExecutor.submit(
                    lambda address: self.sync_address(address.address), cur_receive_address)
                futures.append(future)
            
            cur_change_addresses = self.change_addresses[account_i]
            for index in range(0, len(cur_change_addresses)):
                cur_change_address = cur_change_addresses[index]
                future = esplora.gThreadPoolExecutor.submit(
                    lambda address: self.sync_address(address.address), cur_change_address)
                futures.append(future)

        # Wait for all addresses sync to be completed
        start = time.time()
        for future in as_completed(futures):
            _ = future.result()
            pass

        logging.debug("Sync addresses took {} ms with {} addresses.".format(int((time.time() - start)*1000), len(futures)))

        # Add more unused addresses if any unused addresses are used after the last index
        for addresses, last_address_index, change in [
                (self.receive_addresses, self.last_receive_address_index, 0),
                (self.change_addresses, self.last_change_address_index, 1)]:
            for account_i in range(len(addresses)):
                cur_addresses = addresses[account_i]
                total_address_count = len(cur_addresses)

                # Get the lastest last address index
                cur_last_address_index = last_address_index[account_i]
                updated_last_address_index = cur_last_address_index
                for index in range(cur_last_address_index+1, total_address_count):
                    if cur_addresses[index].last_seen_txid is not None:
                        updated_last_address_index = index

                if updated_last_address_index != cur_last_address_index:
                    # Add more unused addresses to cover the GapLimit
                    new_addresses_needed_count = updated_last_address_index - \
                        cur_last_address_index
                    index = len(cur_addresses)
                    for _ in range(new_addresses_needed_count):
                        pubkey: bytes = self._bip84_path.derive_pubkey(
                            account_i, change, index)
                        p2wpkh = bitcoin.core.CScript([OP_0, Hash160(pubkey)])
                        p2wpkh_addr = P2WPKHBitcoinAddress.from_scriptPubKey(p2wpkh)
                        new_address = Address(
                            False if change == 0 else True, index, account_i, p2wpkh_addr, 0)
                        cur_addresses.append(new_address)
                        self.addresses_map[str(p2wpkh_addr)] = new_address
                        index += 1
                last_address_index[account_i] = updated_last_address_index

        self.syncing = False

    def _utxo_key(self, txid, n):
        return "{}:{}".format(txid, n)

    def sync_address(self, bitcoin_address: CBitcoinAddress):
        address: Address = self.addresses_map[str(bitcoin_address)]
        newest_tx_id = None

        done = False
        synced_txid = None
        head_txid = None
        while not done:
            address_txs_json = esplora.address_txs(bitcoin_address, synced_txid)
            confirmed_tx_count = 0
            for tx_json in address_txs_json:
                if not tx_json["status"]["confirmed"]:
                    continue
                elif head_txid is None:
                    head_txid = tx_json["txid"]

                synced_txid = tx_json["txid"]
                confirmed_tx_count += 1
                if synced_txid == address.last_seen_txid:
                    done = True
                    break

                # For each vin, we find whether there is any UTXO being spent. If so,
                # remove the UTXO and update its address balance.
                for vin in tx_json["vin"]:
                    prevout = vin["prevout"]
                    if prevout["scriptpubkey_address"] == str(bitcoin_address):
                        utxo_key = self._utxo_key(vin["txid"], vin["vout"])
                        if utxo_key not in self.unspent_outputs_map:
                            utxo = UnspentOutput(
                                vin["txid"], vin["vout"], prevout["value"], bitcoin_address)
                            utxo.spent = True
                            self.unspent_outputs_map[utxo_key] = utxo
                        else:
                            utxo = self.unspent_outputs_map[utxo_key]
                            address.balance -= utxo.value
                            self.balance -= utxo.value
                            assert not utxo.spent, "Double spending? txid={}, n={}".format(
                                utxo.txid, utxo.vout)
                            del self.unspent_outputs_map[utxo_key]
                
                for i in range(len(tx_json["vout"])):
                    vout = tx_json["vout"][i]
                    if vout["scriptpubkey_address"] == str(bitcoin_address):
                        utxo_key = self._utxo_key(tx_json["txid"], i)
                        if utxo_key not in self.unspent_outputs_map:
                            utxo = UnspentOutput(
                                tx_json["txid"], i, vout["value"], bitcoin_address)
                            address.balance += utxo.value
                            self.balance += utxo.value
                            self.unspent_outputs_map[utxo_key] = utxo
                        else:
                            utxo = self.unspent_outputs_map[utxo_key]
                            assert utxo.spent
                            # Remove it since it has already been spent.
                            del self.unspent_outputs_map[utxo_key]

            if not done and confirmed_tx_count == 0:
                done = True
                break
        
        address.last_seen_txid = head_txid

    def discover(self):
        """
        Expensive operation
        """
        discover_wallet_result: discovery.DiscoverWalletResult = discovery.discover_bip84_wallet(
            self._seed, Config.GapLimit)
        
        self.receive_addresses = discover_wallet_result.receive_addresses
        self.last_receive_address_index: List[int] = discover_wallet_result.last_receive_address_index
        self.change_addresses: List[List[Address]] = discover_wallet_result.change_addresses
        self.last_change_address_index: List[int] = discover_wallet_result.last_change_address_index

        for cur_account_addresses in self.receive_addresses:
            for address in cur_account_addresses:
                self.addresses_map[str(address.address)] = address

        for cur_account_addresses in self.change_addresses:
            for address in cur_account_addresses:
                self.addresses_map[str(address.address)] = address

        self.sync_addresses()
    
    def request_sync(self):
        # sync is honored if last time sync is more than 5 minutes.
        threshold = 5*60
        if time.time() - self.last_sync > threshold:
            self.sync_addresses()
            self.last_sync = time.time()
    
    def _find_unspent_output(self, txid: str, vout: int) -> UnspentOutput:
        return self.unspent_outputs_map.get(self._utxo_key(txid, vout))
    
    def send(self, value: int, utxos: List[UnspentOutput], destination: CBitcoinAddress, fee=0):
        available_fund = 0
        for i in range(len(utxos)):
            found: UnspentOutput = self._find_unspent_output(
                utxos[i].txid, utxos[i].vout)
            assert found is not None
            # assert not isinstance(
            #     utxos[i].address, P2WPKHBitcoinAddress), "Only suppprot P2WPKH UTXOs."

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
            chnage_address: CBitcoinAddress = self.get_new_change_address()
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
