
NETWORK_MAINNET = "mainnet"
NETWORK_TESTNET = "testnet"

class Config():
    # Either "testnet" or "mainnet"
    Network = NETWORK_TESTNET
    # Gap limit as defined in BIP 44 for account discovery.
    GapLimit = 1
