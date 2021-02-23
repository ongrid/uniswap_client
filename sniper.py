import os
import json
import time
from web3 import Web3
from progress.spinner import Spinner
from web3.gas_strategies.time_based import fast_gas_price_strategy

PRIV_KEY = os.getenv("PRIV_KEY")
WEB3_URL = os.getenv("WEB3_URL")
UNI_ROUTER = os.getenv("UNI_ROUTER", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
UNI_PAIR = os.getenv("UNI_PAIR")

w3 = Web3(Web3.HTTPProvider(WEB3_URL))
w3.eth.setGasPriceStrategy(fast_gas_price_strategy)

account = w3.eth.account.from_key(PRIV_KEY)
print(f"Account: {account.address}")


class Pair:
    w3 = None
    router = None
    block = 0
    contract = None
    token0 = None
    token0_symbol = ""
    token0_reserve = 0
    token0_balance = 0
    token0_allowed = 0
    token1 = None
    token1_symbol = ""
    token1_reserve = 0
    token1_balance = 0
    token1_allowed = 0
    token0_swap_amount = 0
    token1_swap_amount = 0
    tx = None
    route = []
    spend_amount = 0
    rcv_amount = 0
    rcv_token_symbol = 0
    gas_price = 0

    def __init__(self, w3):
        self.w3 = w3
        with open("uniswap_router.abi", "r") as abi_file:
            uniswap_router_abi = json.load(abi_file)
        self.router = self.w3.eth.contract(abi=uniswap_router_abi, address=UNI_ROUTER)

    def set_pair(self, address):
        with open("uniswap_pair.abi", "r") as abi_file:
            uniswap_pair_abi = json.load(abi_file)
        with open("erc20.abi", "r") as abi_file:
            erc20_abi = json.load(abi_file)
        self.contract = w3.eth.contract(abi=uniswap_pair_abi, address=address)
        self.factory = self.router.functions.factory().call()
        token0_address = self.contract.functions.token0().call()
        token1_address = self.contract.functions.token1().call()
        self.token0 = w3.eth.contract(abi=erc20_abi, address=token0_address)
        self.token1 = w3.eth.contract(abi=erc20_abi, address=token1_address)
        (
            self.token0_reserve,
            self.token1_reserve,
            time,
        ) = self.contract.functions.getReserves().call()
        self.block = self.w3.eth.block_number - 100
        self.token0_symbol = self.token0.functions.symbol().call()
        self.token1_symbol = self.token1.functions.symbol().call()
        self.name = f"{self.token0_symbol}_{self.token1_symbol}"
        self.token0_balance = self.token0.functions.balanceOf(account.address).call()
        self.token1_balance = self.token1.functions.balanceOf(account.address).call()
        self.token0_allowance = self.token0.functions.allowance(
            account.address, UNI_ROUTER
        ).call()
        self.token1_allowance = self.token1.functions.allowance(
            account.address, UNI_ROUTER
        ).call()
        self.token0_swap_amount = min(self.token0_balance, self.token0_allowance)
        self.token1_swap_amount = min(self.token1_balance, self.token1_allowance)

        print(f"Pair {self.name}")
        print(f"  Token0 {self.token0.functions.symbol().call()}")
        print(
            f"    price 1 {self.token0.functions.symbol().call()} = {self.router.functions.getAmountsOut(amountIn=int(1e18), path=[self.token0.address, self.token1.address]).call()[1]/1e18} {self.token1.functions.symbol().call()}"
        )
        print(f"    reserve {self.token0_reserve / 1e18}")
        print(f"    swapable on your acc {self.token0_swap_amount / 1e18}")
        print(f"  Token1 {self.token1.functions.symbol().call()}")
        print(
            f"    price 1 {self.token1.functions.symbol().call()} = {self.router.functions.getAmountsOut(amountIn=int(1e18), path=[self.token1.address, self.token0.address]).call()[1]/1e18} {self.token0.functions.symbol().call()}"
        )
        print(f"    reserve {self.token1_reserve / 1e18}")
        print(f"    swapable on your acc {self.token1_swap_amount / 1e18}")

    def build_and_send_tx(self):
        nonce = self.w3.eth.getTransactionCount(account.address)
        while True:
            try:
                tx = self.router.functions.swapExactTokensForTokens(
                    amountIn=self.spend_amount,
                    amountOutMin=self.rcv_amount,
                    path=self.path,
                    to=account.address,
                    deadline=1615000000,
                ).buildTransaction(
                    {
                        "from": account.address,
                        "nonce": nonce,
                        "gasPrice": self.gas_price,
                        "gas": 200000,
                    }
                )
                print(tx)
                signed = self.w3.eth.account.sign_transaction(tx, account.key)
                print(f"TX hash: {signed.hash.hex()}")
                tx_hash = self.w3.eth.sendRawTransaction(signed.rawTransaction)
                tx_receipt = self.w3.eth.waitForTransactionReceipt(tx_hash)
                break
            except Exception as exc:
                print("Something went wrong")
                print(exc)
                time.sleep(1)
        print("DONE!")

    def get_token_by_symbol(self, symbol):
        if symbol == self.token0_symbol:
            return self.token0
        if symbol == self.token1_symbol:
            return self.token1
        return None

    def set_desire(
        self, spend_token="WETH", spend_amount=0, rcv_token="UNI", rcv_amount=0
    ):
        spend = self.get_token_by_symbol(spend_token)
        rcv = self.get_token_by_symbol(rcv_token)
        self.path = [spend.address, rcv.address]
        self.spend_amount = int(spend_amount * 1e18)
        self.rcv_amount = int(rcv_amount * 1e18)
        self.rcv_token_symbol = rcv_token

    def set_gas_price(self, gas_price):
        if gas_price == "auto":
            print(f"Auto-generate gas price. It can take several minutes")
            self.gas_price = int(self.w3.eth.generateGasPrice() * 1.1)

        else:
            self.gas_price = gas_price
        print(f"Gas price is {self.gas_price} wei or {self.gas_price / 1e9} Gwei")

    def wait_desired_conditions(self):
        spinner = Spinner()
        rcv_current = None
        while True:
            prev_rcv = rcv_current
            rcv_current = self.router.functions.getAmountsOut(
                amountIn=self.spend_amount, path=self.path
            ).call()[1]
            if rcv_current != prev_rcv:
                print("")
                spinner.message=f"Expected: {self.rcv_amount} {self.rcv_token_symbol}, Current: {rcv_current} "
            spinner.next()
            if rcv_current >= self.rcv_amount:
                print("\nConditions are met!")
                return True
            time.sleep(0.5)


p = Pair(w3)
p.set_gas_price(180_000_000_000)
p.set_pair(UNI_PAIR)
p.set_desire(spend_token="WETH", spend_amount=10, rcv_token="UNI", rcv_amount=513.4)
p.wait_desired_conditions()
p.build_and_send_tx()
