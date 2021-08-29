
from flask import request, redirect, url_for, Response
import hashlib
import time
from bitcoin import base58
from functools import wraps
import logging
from config import Config
import os
import random

def compute_secret(passphrase: str) -> bytes:
    prefix = b'welcome to use Open Wallet: '
    assert len(passphrase) >= 8

    passphrase = passphrase.encode()
    passphrase = prefix + passphrase
    for _ in range(32):
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


##### Flask related ######
class LoggedInUser():
    def __init__(self):
        self.client_cookie = ""
        time.time()
        # UNIX time.
        self.exp_at = 0

LOGIN_GOOD_FOR = 60*60
CLIENT_COOKIE_NAME = "LOGGED_IN_USER"

gLoggedInUser = LoggedInUser()

def login(passphrase: str, response: Response) -> str:
    """
    return cookie upon success, otherwise exception.
    """
    # Delay for preventing brute force attack.
    time.sleep(1)
    assert verify_passphrase(passphrase), "Failed to login."

    gLoggedInUser.client_cookie = base58.encode(os.urandom(32))
    gLoggedInUser.exp_at = time.time() + LOGIN_GOOD_FOR
    response.set_cookie(CLIENT_COOKIE_NAME,
                        gLoggedInUser.client_cookie)
    return gLoggedInUser.client_cookie

def logout(response: Response):
    response.set_cookie(CLIENT_COOKIE_NAME, '', expires=0)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if Config.EnableLogin:
            if gLoggedInUser.exp_at < time.time() or request.cookies.get(CLIENT_COOKIE_NAME) != gLoggedInUser.client_cookie:
                return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

    
