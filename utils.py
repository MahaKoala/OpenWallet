import sqlite3
from typing import List, Set, Dict, Tuple
from mnemonic import Mnemonic
import bitcoin
import logging
import os
import discovery
from wallet import Wallet, UnspentOutput
from config import Config

SQLITE_DB_FILE = os.path.dirname(
    os.path.realpath(__file__)) + "/data/wallets.db"

EnglishMnemonic = Mnemonic("english")

class AddressView():
    def __init__(self, bitcoin_address: str, value: int, is_change: bool, derivation_path: str):
        self.bitcoin_address = bitcoin_address
        self.omitted_bitcoin_address = bitcoin_address[0:4] + \
            "..." + bitcoin_address[-4:]
        self.value = value
        self.is_change = is_change
        # https://docs.python.org/3/library/string.html#format-specification-mini-language
        # The ',' option signals the use of a comma for a thousands separator. For a locale aware separator,
        # use the 'n' integer presentation type instead.
        self.formatted_value = '{:,}'.format(value)
        self.derivation_path = derivation_path

class WalletMempoolTransactionView():
    def __init__(self, txid, value):
        self.txid = txid
        self.omitted_txid = self.txid[0:3] + "..." + self.txid[-4:]
        self.value = value

class UnspentOutputView():
    def __init__(self, unspent_output: UnspentOutput):
        self.bitcoin_address = str(unspent_output.address)
        self.omitted_bitcoin_address = self.bitcoin_address[0:4] + \
            "..." + self.bitcoin_address[-4:]
        self.formatted_value = '{:,}'.format(unspent_output.value)
        self.value = unspent_output.value
        self.vout = unspent_output.vout
        self.txid = unspent_output.txid
        self.omitted_txid = self.txid[0:3] + "..." + self.txid[-4:]
        self.sent = unspent_output.sent

class WalletView():
    def __init__(self, wallet_id: int, network, label):
        self.wallet_id = wallet_id
        self.network = network
        self.label = label

    def _loadwallet(self, wallet: Wallet, show_zero_balance: int = 0):
        self.balance = wallet.balance
        self.formatted_balance = '{:,}'.format(wallet.balance)

        self.addresses: List[AddressView] = []
        
        for addr in wallet.addresses_map.values():
            derivation_path = wallet.path_prefix + \
                "/{}/{}".format(1 if addr.is_change else 0, addr.address_index)
            if addr.balance != 0:
                self.addresses.append(AddressView(
                    str(addr.address), addr.balance, addr.is_change, derivation_path))
            elif show_zero_balance == 1:
                self.addresses.append(AddressView(
                    str(addr.address), addr.balance, addr.is_change, derivation_path))
        self.addresses.sort(key=lambda addr: addr.derivation_path.split("/"))

        self.unspent_outputs = [] 
        for unspent_output in wallet.unspent_outputs_map.values():
            self.unspent_outputs.append(UnspentOutputView(unspent_output))     
        self.unspent_outputs.sort(
            key=lambda unspent_output: (unspent_output.bitcoin_address, unspent_output.txid, unspent_output.vout))

        self.mempool_txs: List[WalletMempoolTransactionView] = []
        for mempool_tx in wallet.mempool_tx_map.values():
            self.mempool_txs.append(
                WalletMempoolTransactionView(mempool_tx.txid, mempool_tx.value))
    
gWalletMap: Dict[int, Tuple[WalletView, Wallet]]={}

def addwallet(nemonic: str, label: str) -> bool:
    assert validate_nemonic(nemonic) == None

    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Wallets (network, mnemonic, label) VALUES (?,?,?)", (Config.Network, nemonic, label))
        conn.commit()
    return True

def newaddress(wallet_id: int) -> str:
    wallet: Wallet = gWalletMap[wallet_id][1]
    assert len(wallet.receive_addresses) > 0, "Account 0 must be present."
    
    last_index = wallet.last_receive_address_index[0]
    return str(wallet.receive_addresses[0][last_index+1].address)

def viewwallet(wallet_id: int, show_zero_balance) -> WalletView:
    # Return the wallet from the cache if found.
    if wallet_id in gWalletMap.keys():
        wallet = gWalletMap[wallet_id][1]

        wallet_view = gWalletMap[wallet_id][0]
        wallet_view._loadwallet(wallet, show_zero_balance)
        return wallet_view

    # Load from the database
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, network, mnemonic, label FROM Wallets WHERE id = ?", (wallet_id,))
        row = cursor.fetchone()
        assert row is not None

        wallet_id, network, mnemonic, label = row
        seed = Mnemonic.to_seed(mnemonic)
        wallet = Wallet(seed)
        wallet.discover()
        wallet.sync_addresses()
        wallet_view = WalletView(wallet_id, network, label)
        wallet_view._loadwallet(wallet, show_zero_balance)
        gWalletMap[wallet_id] = (wallet_view, wallet)
        return wallet_view

def request_sync(wallet_id: int):
    assert wallet_id in gWalletMap.keys()
    wallet = gWalletMap[wallet_id][1]
    wallet.request_sync()

'''
return None if nemonic is valid, otherwise error message.
'''
def validate_nemonic(nemonic: str) -> str:
    if not EnglishMnemonic.check(nemonic):
        return "Invalid nemonic."
    return None

def loadwallets() -> List[WalletView]:
    wallets = []
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, network, mnemonic, label FROM Wallets")
        for row in cursor:
            wallet_id, network, mnemonic, label = row
            if Config.Network == network:
                wallets.append(WalletView(wallet_id, network, label))
    return wallets

def send(wallet_id: int, value: int, fee: int, utxos: List[Tuple[str, int]], destination: str) -> Tuple[str, int]:
    unspent_outputs = [UnspentOutput(
        utxo[0], utxo[1], None, None) for utxo in utxos]
    bitcoin_address = bitcoin.wallet.CBitcoinAddress(destination)

    assert wallet_id in gWalletMap, "Wallet not found."
    wallet: Wallet = gWalletMap[wallet_id][1]
    return wallet.send(value, unspent_outputs, bitcoin_address, fee=fee)

def fee_estimates(wallet_id: int, utxos: List[Tuple[str, int]], destination: str) -> Dict[int, int]:
    unspent_outputs = [UnspentOutput(
        utxo[0], utxo[1], None, None) for utxo in utxos]
    bitcoin_address = bitcoin.wallet.CBitcoinAddress(destination)
    assert wallet_id in gWalletMap, "Wallet not found."
    wallet: Wallet = gWalletMap[wallet_id][1]

    return wallet.fee_estimates(unspent_outputs, bitcoin_address)
