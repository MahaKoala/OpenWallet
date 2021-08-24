import os

NETWORK_MAINNET = "mainnet"
NETWORK_TESTNET = "testnet"

class FullNodeConfig:
    def __init__(self, config_file):
        """
        @rpc_user_password: path to a file that store user and password to access the node.
        """
        with open(config_file) as f:
            for line in f:
                line = line.strip()
                tokens = line.split("=")
                assert len(tokens) == 2, "invalid config file: {}".format(config_file)

                if tokens[0] == "host":
                    self.host = tokens[1]
                elif tokens[0] == "port":
                    self.port = tokens[1]
                elif tokens[0] == "user":
                    self.user = tokens[1]
                elif tokens[0] == "password":
                    self.password = tokens[1]
                else:
                    raise "Unrecognized key {}".format(tokens[0])

class Config():
    # Either "testnet" or "mainnet"
    Network = NETWORK_TESTNET

    # Gap limit as defined in BIP 44 for account discovery.
    GapLimit = 2

    # The prefix of endpoint that displays bitcoin data. supports
    # 1. Bitcoin address: the link is <DashboardPrefix>/address/<address>
    ExplorerPrefix = "https://blockstream.info"

    # Same as "ExplorerPrefix", except it is for testnet.
    TestNetExplorerPrefix = "https://blockstream.info/testnet"

    # Endpoint to an instance of Esplora (https://github.com/Blockstream/esplora)
    EsploraEndpoint = "https://blockstream.info/api/"

    # Same as "EsploraEndpoint", except it is for testnet.
    TestNetExploraEndpoint = "https://blockstream.info/testnet/api/"

    FullNodeConfig: FullNodeConfig(os.path.dirname(os.path.abspath(__file__)) + "/.fullnode_connection.conf")

    TestNetFullNodeConfig = FullNodeConfig(
        os.path.dirname(os.path.abspath(__file__)) +
                        "/.fullnode_connection.testnet.conf")

    # Opt-in Full Replace-by-Fee Signaling
    # Reference: https://github.com/bitcoin/bips/blob/master/bip-0125.mediawiki
    EnableBip125Rfb = True

    # Can be enabled only if a running Bitcoin Full Node (Bitcoin Core) 
    EnableSendTx = True

    ThreadPoolMaxWorkers = 10
