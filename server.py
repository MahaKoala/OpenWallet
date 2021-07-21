import sqlite3
from flask import Flask, render_template, Response, send_from_directory, jsonify
from flask import request
from utils import loadwallets, validate_nemonic
import utils
import json
import os
from config import Config, NETWORK_MAINNET, NETWORK_TESTNET
import logging
import bitcoin
import os

app = Flask(__name__)
if app.env == 'development':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
else:
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

if Config.Network == NETWORK_MAINNET:
    logging.debug("Selecting mainnet")
    bitcoin.SelectParams("mainnet")
else:
    logging.debug("Selecting testnet")
    bitcoin.SelectParams("testnet")

# global variable to all templates
if Config.Network == NETWORK_MAINNET:
    app.jinja_env.globals['g_network_type'] = "Main Net"
    app.jinja_env.globals['g_explorer'] = Config.ExplorerPrefix
else:
    app.jinja_env.globals['g_network_type'] = "Test Net"
    app.jinja_env.globals['g_explorer'] = Config.TestNetExplorerPrefix

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

@app.route('/css/<path:path>')
def send_css(path):
    return send_from_directory('css', path)

@app.route('/addwallet')
def addwallet():
    return render_template('addwallet.html')

@app.route('/viewwallet/<wallet_id>')
def viewwallet(wallet_id):
    wallet: Wallet = utils.viewwallet(wallet_id)
    return render_template('viewwallet.html', wallet=wallet)

@app.route('/')
def index():
    wallets = loadwallets()
    network = "Main Net" if Config.Network == NETWORK_MAINNET \
        else "Test Net"
    return render_template('index.html', wallets=wallets)

''' REST API '''
@app.route('/api/v1/addwallet', methods=['POST'])
def api_addwallet():
    req = json.loads(request.data)
    validation_result = validate_nemonic(req["nemonic"])
    if validation_result is not None:
        return jsonify({
            'error': 'nemonic is not valid', 
            'detail': validation_result
        }), 400
    
    if not utils.addwallet(req["nemonic"], req["label"]):
        return jsonify({
            'error': 'addwallet fails',
            'detail': ""
        }), 500

    return jsonify({}), 200
