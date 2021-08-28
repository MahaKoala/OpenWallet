
import hashlib
from bitcoin import base58
import logging
import os

def compute_secret(passphrase: str) -> bytes:
    prefix = b'welcome to use Open Wallet: '
    assert len(passphrase) >= 8

    passphrase = passphrase.encode()
    passphrase = prefix + passphrase
    for _ in range(128):
        passphrase = hashlib.sha256(passphrase).digest()
    return passphrase
    
def verify_passphrase(passphrase: str):    
    secret_file = os.path.dirname(os.path.abspath(
        __file__)) + "/access.secret"

    assert os.path.exists(secret_file), "Please setup passpharase before use it"
    with open(secret_file) as f:
        real_secret_base58 = f.read()
        real_secret: bytes = base58.decode(real_secret_base58)
        
        secret = compute_secret(passphrase)
        if secret != real_secret:
            logging.debug("{} != {}".format(secret, real_secret))
            return False
        else:
            return True

    
