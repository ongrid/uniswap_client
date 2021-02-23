# Uniswap pythonic client

This software is unstable and has been NEVER tested. Use it at own risk.

## Install dependencies

```sh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configure

Top up the ethereum account with enough amount of Ether (to pay gas for txes) and token you are going to spend.

Approve the token you are going to spend. It's not implemented yet. You can do it using addLiquidity DApp on Uniswap.

Export hex-encoded private key to the environment

```sh
export PRIV_KEY=deafbeefdeafbeefdeafbeefdeafbeefdeafbeefdeafbeefdeafbeefdeafbeef
export UNI_PAIR=0xd3d2E2692501A5c9Ca623199D38826e513033a17
export UNI_ROUTER=0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D
export WEB3_URL=https://mainnet.infura.io/v3/YOUR_INFURA_ID
```

Edit the last lines of the `sniper.py` and configure the purchase conditions

```python
# this means that sniper will monitor until spending 10 WITH gives 513.4 UNI"""
p.set_desire(spend_token="WETH", spend_amount=10, rcv_token="UNI", rcv_amount=513.4)
# sleep until conditions get satisfied
p.wait_desired_conditions()
# once it get triggered the next line signs and sends tx to the network
p.build_and_send_tx()
```

## Run

Start and see what happens

```sh
source venv/bin/activate
python sniper.py
```
