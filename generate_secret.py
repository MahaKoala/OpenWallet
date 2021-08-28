from getpass import getpass
from auth import compute_secret
from bitcoin import base58
import os

if __name__ == '__main__':
    passphrase = getpass("Enter passphrase: ")
    passphrase2 = getpass("Enter passphrase again: ")
    assert passphrase2 == passphrase, "passphrase does not match."

    secret = compute_secret(passphrase)
    secret_file = os.path.dirname(os.path.abspath(
        __file__)) + "/access.secret"
    with open(secret_file, "w") as f:
        f.write(base58.encode(secret))

    
