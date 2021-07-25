
NETWORK_MAINNET = "mainnet"
NETWORK_TESTNET = "testnet"

class Config():
    # Either "testnet" or "mainnet"
    Network = NETWORK_TESTNET

    # Gap limit as defined in BIP 44 for account discovery.
    GapLimit = 1

    # The prefix of endpoint that displays bitcoin data. supports
    # 1. Bitcoin address: the link is <DashboardPrefix>/address/<address>
    ExplorerPrefix = "https://blockstream.info"

    # Same as "ExplorerPrefix", except it is for testnet.
    TestNetExplorerPrefix = "https://blockstream.info/testnet"

    # Endpoint to an instance of Esplora (https://github.com/Blockstream/esplora)
    EsploraEndpoint = "https://blockstream.info/api/"

    # Same as "EsploraEndpoint", except it is for testnet.
    TestNetExploraEndpoint = "https://blockstream.info/testnet/api/"

    ThreadPoolMaxWorkers = 10
