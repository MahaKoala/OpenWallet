import sqlite3
from flask import Flask, render_template, Response, send_from_directory, jsonify
from flask import request
from utils import loadwallets, validate_nemonic
import utils
import json
import os
from config import Config, NETWORK_MAINNET, NETWORK_TESTNET

app = Flask(__name__)
is_mainnet = False

@app.route('/js/<path:path>')
def send_js(path):
    return send_from_directory('js', path)

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
    return render_template('index.html', wallets=wallets, g_network_type=network)

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

if __name__ == '__main__':
    if Config.Network == NETWORK_MAINNET:
        bitcoin.SelectParams("mainnet")
    else:
        bitcoin.SelectParams("testnet")

    # global variable to all templates
    app.jinja_env.globals['g_network_type'] = "Main Net" if Config.Network == NETWORK_MAINNET \
        else "Test Net"

    app.run(host='localhost')
