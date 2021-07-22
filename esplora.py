import requests
from requests import Response
from bitcoin.wallet import CBitcoinAddress
from config import Config, NETWORK_MAINNET
import logging

ENDPOINT_TESTNET = Config.TestNetExploraEndpoint
ENDPOINT_MAINNET = Config.EsploraEndpoint

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

# Returns true if the address exists on the blockchain.
def existaddress(bitcoinaddr: CBitcoinAddress) -> bool:
    response = http_get(
        "%saddress/%s" % (getendpoint(), str(bitcoinaddr)))
    assert response.status_code == 200, ("HTTP Error: %s" % (response.text,))

    json = response.json()
    if json["chain_stats"]["tx_count"] != 0:
        return True

    return False

class AddressResponse:
    def __init__(self, balance):
        self._balance = balance

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

