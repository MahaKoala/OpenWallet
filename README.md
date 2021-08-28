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

# Run on HTTPS
Requires `openssl` installed. Unfortunately Chrome is supported using this instruction.
Safari and Firefox is supported. If you see a warning from Firefox, click on `Advance` 
and `Accept the risk and Continue`.
```sh
# Create a self-signed certificate
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Import cert.pem to the browswer. On macbook, you can import it using `Keychain Access`

# Start the application with certificate
FLASK_APP=server.py FLASK_ENV=development flask run --cert=cert.pem --key=key.pem
```

# Assumption on using OpenWallet
* Only a single user per instance of OpenWallet.

# JS dependencies
* QR code generation code is borrowed from https://github.com/nimiq/qr-creator.