import sqlite3
from typing import List, Set
from mnemonic import Mnemonic
import bitcoin
import logging
import os
import discovery
from config import Config

SQLITE_DB_FILE = os.path.dirname(
    os.path.realpath(__file__)) + "/data/wallets.db"

EnglishMnemonic = Mnemonic("english")

class Wallet(discovery.Wallet):
    def __init__(self, id, network, mnemonic, label):
        self._id = id
        self._network = network
        self._mnemonic = mnemonic
        self._label = label
    
    def merge(self, wallet: discovery.Wallet):
        self._balance = wallet._balance
        self._addresses = wallet._addresses
        
    @classmethod
    def fromdb(cls, row):
        return Wallet(*row)

def addwallet(nemonic: str, label: str) -> bool:
    assert validate_nemonic(nemonic) == None

    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Wallets (network, mnemonic, label) VALUES (?,?,?)", (Config.Network, nemonic, label))
        conn.commit()
    return True

def viewwallet(wallet_id) -> Wallet:
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, network, mnemonic, label FROM Wallets WHERE id = ?", (wallet_id,))
        row = cursor.fetchone()
        assert row is not None

        wallet: Wallet = Wallet.fromdb(row)
        seed = Mnemonic.to_seed(wallet._mnemonic)
        wallet.merge(discovery.discover_bip84_wallet(seed, gap_limit=Config.GapLimit))
        return wallet

'''
return None if nemonic is valid, otherwise error message.
'''
def validate_nemonic(nemonic: str) -> str:
    if not EnglishMnemonic.check(nemonic):
        return "Invalid nemonic."
    return None

def loadwallets() -> List[Wallet]:
    wallets = []
    with sqlite3.connect(SQLITE_DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, network, mnemonic, label FROM Wallets")
        for row in cursor:
            wallet = Wallet.fromdb(row)
            if Config.Network == wallet._network:
                wallets.append(wallet)
    return wallets

