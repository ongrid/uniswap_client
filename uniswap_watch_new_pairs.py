import os
import json
import time
from web3 import Web3
import argparse
from progress.spinner import Spinner

parser = argparse.ArgumentParser(
    description="Find new Uniswap pairs"
)
parser.add_argument("--lookback")
parser.add_argument("--whitelisted")
args = parser.parse_args()
if args.lookback:
    lookback = int(args.lookback)
else:
    lookback = 0

if args.whitelisted:
    whitelisted = Web3.toChecksumAddress(args.whitelisted)
else:
    whitelisted = None

WEB3_URL = os.getenv("WEB3_URL")
UNI_ROUTER = os.getenv("UNI_ROUTER", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
UNI_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

w3 = Web3(Web3.HTTPProvider(WEB3_URL, request_kwargs={"timeout": 120}))

with open("uniswap_router.abi", "r") as abi_file:
    uniswap_router_abi = json.load(abi_file)
router = w3.eth.contract(abi=uniswap_router_abi, address=UNI_ROUTER)

with open("uniswap_pair.abi", "r") as abi_file:
    uniswap_pair_abi = json.load(abi_file)

with open("uniswap_factory.abi", "r") as abi_file:
    uniswap_factory_abi = json.load(abi_file)
factory = w3.eth.contract(abi=uniswap_factory_abi, address=UNI_FACTORY)

with open("erc20.abi", "r") as abi_file:
    erc20_abi = json.load(abi_file)

def show_pair(pair_id):
    pair_addr = Web3.toChecksumAddress(factory.functions.allPairs(pair_id).call())
    pair = w3.eth.contract(abi=uniswap_pair_abi, address=pair_addr)
    token0_addr = Web3.toChecksumAddress(pair.functions.token0().call())
    token1_addr = Web3.toChecksumAddress(pair.functions.token1().call())
    if whitelisted:
        if whitelisted not in (token0_addr, token1_addr):
            return
    token0 = w3.eth.contract(abi=erc20_abi, address=token0_addr)
    token1 = w3.eth.contract(abi=erc20_abi, address=token1_addr)
    token0_symbol = token0.functions.symbol().call()
    token1_symbol = token1.functions.symbol().call()
    token0_decimals = int(token0.functions.decimals().call())
    token1_decimals = int(token1.functions.decimals().call())
    print(f"\nPair found:{pair_addr} ({token0_symbol} {token1_symbol})")
    print(f"  Token0: {token0_addr} ({token0_symbol})")
    print(f"  Token1: {token1_addr} ({token1_symbol})")
    print(
        f"  price 1 {token0_symbol} = {router.functions.getAmountsOut(amountIn=int(10 ** token0_decimals), path=[token0.address, token1.address]).call()[1]/10 ** token1_decimals} {token1_symbol}"
    )
    print(
        f"  price 1 {token1_symbol} = {router.functions.getAmountsOut(amountIn=int(10 ** token1_decimals), path=[token1.address, token0.address]).call()[1]/10 ** token0_decimals} {token0_symbol}"
    )
    print("")

factory = w3.eth.contract(abi=uniswap_factory_abi, address=UNI_FACTORY)
num = factory.functions.allPairsLength().call()

print(f"Now there are {num} pairs")
print(f"We look {lookback} pairs back")
if whitelisted:
    whitelisted_token = w3.eth.contract(abi=erc20_abi, address=whitelisted)
    whitelisted_token_symbol = whitelisted_token.functions.symbol().call()
    print(f"and show pairs with whitelisted token {whitelisted_token_symbol} ({whitelisted})")

for i in range(num-lookback, num):
    show_pair(i)

sp = Spinner(f"Looking for new pairs ")
while True:
    new_num = factory.functions.allPairsLength().call()
    if new_num > num:
        num = new_num
        show_pair(num)
    sp.next()
    time.sleep(0.5)
