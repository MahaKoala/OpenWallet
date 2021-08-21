import requests
from requests import Response
from bitcoin.wallet import CBitcoinAddress
from bitcoin.core import CScript, CTxOut, CTransaction
from config import Config, NETWORK_MAINNET
import binascii
from wallet import UnspentOutput
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Set, Dict
import time

ENDPOINT_TESTNET = Config.TestNetExploraEndpoint
ENDPOINT_MAINNET = Config.EsploraEndpoint

gThreadPoolExecutor: ThreadPoolExecutor = ThreadPoolExecutor(
    Config.ThreadPoolMaxWorkers)

def getendpoint():
    return ENDPOINT_MAINNET if Config.Network == NETWORK_MAINNET else ENDPOINT_TESTNET

def http_get(url, retry_on_5xx=True) -> Response:
   response = requests.get(url)
   if response.status_code >= 500:
      logging.debug("Retrying " + url)

      # Try again.
      sleep(0.5)
      response = requests.get(url)
   return response

gExistedAddresses = set()
def existaddress(bitcoinaddr: CBitcoinAddress) -> bool:
    if str(bitcoinaddr) in gExistedAddresses:
        return True
    response = http_get(
        "%saddress/%s" % (getendpoint(), str(bitcoinaddr)))
    assert response.status_code == 200, ("HTTP Error: %s" % (response.text,))

    json = response.json()
    if json["chain_stats"]["tx_count"] != 0:
        gExistedAddresses.add(str(bitcoinaddr))
        return True

    return False

class AddressResponse:
    def __init__(self, balance):
        self.balance = balance

def address(address: CBitcoinAddress) -> AddressResponse:
    addr_url = "{endpoint}address/{addr}"
    response = http_get(addr_url.format(
        endpoint=getendpoint(), addr=str(address)))
    assert response.status_code == 200, "Failed to get address"
    json = response.json()
    balance = json["chain_stats"]["funded_txo_sum"] - \
        json["chain_stats"]["spent_txo_sum"]
    response = AddressResponse(balance)
    return response

def addresses(addresses: [CBitcoinAddress]) -> List[AddressResponse]:
    future_addresses = [gThreadPoolExecutor.submit(
        address, addr) for addr in addresses]
    address_responses = []
    start_time = time.time()
    for future_address in as_completed(future_addresses):
        address_responses.append(future_address.result())
    logging.debug("Took %d ms to complete addresses" % ((time.time() - start_time)*1000, ))
    return address_responses

'''
Retrives the set of utxo
'''
def utxo(address: CBitcoinAddress) -> Set[UnspentOutput]:
    utxo_url = "{endpoint}address/{addr}/utxo"
    response = http_get(utxo_url.format(
        endpoint=getendpoint(), addr=str(address)))
    assert response.status_code == 200, "Failed to get utxo of " + str(address)
    json = response.json()
    utxos = set()
    for elm in json:
        if elm["status"]["confirmed"]:
            utxos.add(UnspentOutput(
                elm["txid"], elm["vout"], elm["value"], address))
    return utxos

def utxos(addresses: List[CBitcoinAddress]) -> Dict[str, Set[UnspentOutput]]:
    future_utxos = [gThreadPoolExecutor.submit(
        utxo, addr) for addr in addresses]
    utxos_response = {}
    start_time = time.time()
    index = 0
    for future_utxo in as_completed(future_utxos):
        address = addresses[index]
        utxos_response[str(address)] = future_utxo.result()
        index += 1
    logging.debug("Took %d ms to complete utxos" % ((time.time() - start_time)*1000, ))
    return utxos_response

def txout(utxo: UnspentOutput) -> CTxOut:
    tx_url = "{endpoint}tx/{txid}"
    tx_response = http_get(tx_url.format(
        endpoint=getendpoint(), txid=utxo.txid))
    assert tx_response.status_code == 200, "Failed to get transaction of ID " + utxo.txid

    tx_json = tx_response.json()
    assert utxo.vout < len(tx_json["vout"]), "utxo vout is out of the bound (txid={}, vout={})".format(utxo.txid,  utxo.vout)    
    txout_json = tx_json["vout"][utxo.vout]
    b = binascii.unhexlify(txout_json["scriptpubkey"])
    scriptpubkey: CScript = CScript(b)
    return CTxOut(nValue=txout_json["value"], scriptPubKey=scriptpubkey)

def txouts(utxos: List[UnspentOutput]) -> List[CTxOut]:
    future_txouts = [gThreadPoolExecutor.submit(
        txout, utxo) for utxo in utxos]
    txouts = []
    start_time = time.time()
    for future_txout in as_completed(future_txouts):
        txouts.append(future_txout.result())
    logging.debug("Took %d ms to complete txouts" %
                  ((time.time() - start_time)*1000, ))
    return txouts

def tx(tx: CTransaction) -> str:
    # return tx.GetTxid()

    # POST /tx
    tx_url = "{endpoint}tx"
    response = requests.post(tx_url.format(
        endpoint=getendpoint()), data=str(tx.serialize()))
    if response.status_code != 200:
        logging.warn("Send transaction failed: " + response.text)
        return ""
    assert response.text() == str(tx.GetTxid())
    return str(tx.GetTxid())

# def tx(txid) -> CTransaction:
#     '''
#     @txid: hex of the transaction ID 

#     @return:
#     '''
#     tx_url = "{endpoint}tx/{txid}"
#     response = http_get(tx_url.format(endpoint=getendpoint(), addr=txid))
#     assert response.status_code == 200, "Failed to get transaction of ID " + txid
#     json = response.json()
#     txid


    
