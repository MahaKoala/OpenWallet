# OpenWallet
Bitcoin hot wallet web app

# Get Started
```shell
cd <path to this directory>
python3 -m venv .
. bin/activate
pip install --upgrade pip
pip install -r requirements.txt 
python initdb.py
FLASK_APP=server.py FLASK_ENV=development flask run
```

For the future run
```
. bin/activate
FLASK_APP=server.py FLASK_ENV=development flask run
```

# Configuration
Modify `config.py` for
* Select testnet or mainnet.

# Assumption on using OpenWallet
* Only a single user per instance of OpenWallet.

# JS dependencies
* QR code generation code is borrowed from https://github.com/nimiq/qr-creator.