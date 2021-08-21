import requests
import binascii
import struct
from config import Config, NETWORK_MAINNET, NETWORK_TESTNET

def make_request(payload):
    full_node_config = None
    if Config.Network == NETWORK_TESTNET:
        assert Config.TestNetFullNodeConfig is not None, "Missing TestNetFullNodeConfig"
        full_node_config = Config.TestNetFullNodeConfig
    elif Config.Network == NETWORK_MAINNET:
        assert Config.FullNodeConfig is not None, "Missing FullNodeConfig"
        full_node_config = Config.FullNodeConfig
    else:
        raise "Unknown network type: {}".format(Config.Network)

    jsonrpc_server = "http://{}:{}".format(
        full_node_config.host, full_node_config.port)
    user = full_node_config.user
    password = full_node_config.password
    
    response = requests.post(jsonrpc_server, json=payload, auth=(
        user, password)).json()

    return response


gFullnode_sendrawtransactionId = 0
def sendrawtransaction(rawtx: bytes) -> str:
    """
    @return: hex-encoded txid.
    """
    # FIXME: Not thread safe though
    global gFullnode_sendrawtransactionId
    gFullnode_sendrawtransactionId += 1

    payload = {
        'method': "sendrawtransaction",
        'params': [binascii.hexlify(rawtx).decode("ascii")],
        'jsonrpc': '1.0',
        'id': gFullnode_sendrawtransactionId
    }
    response = make_request(payload)
    assert response['error'] == None, "sendrawtransaction failed: {}".format(response['error'])
    return response['result']

