import os
import json
import time
from web3 import Web3
from web3.gas_strategies.time_based import fast_gas_price_strategy

WEB3_URL = os.getenv("WEB3_URL")
UNI_ROUTER = os.getenv("UNI_ROUTER", "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
UNI_PAIR = os.getenv("UNI_PAIR")
UNI_PAIR = '0x2F85E11f6F12eaD6Af643F083a34E001030D2a6F'

w3 = Web3(Web3.HTTPProvider(WEB3_URL, request_kwargs={'timeout': 120}))

with open("uniswap_router.abi", "r") as abi_file:
    uniswap_router_abi = json.load(abi_file)
router = w3.eth.contract(abi=uniswap_router_abi, address=UNI_ROUTER)

with open("uniswap_pair.abi", "r") as abi_file:
    uniswap_pair_abi = json.load(abi_file)
pair = w3.eth.contract(abi=uniswap_pair_abi, address=UNI_PAIR)

class Log:
    def __init__(self, event=None, attributes={}):
        self.event = event
        self.attributes= attributes

class Tx:
    hash = None
    def __init__(self, hash=None, to=None, input=None):
        self.hash = hash
        self.to = to
        self.input = input
        self.target_contract = None
        self.decoded = None
        self.logs = {}
    def decode(self):
        if self.to == UNI_ROUTER:
            self.target_contract = router
        if self.to == UNI_PAIR:
            self.target_contract = pair
        if self.target_contract:
            decode_result=self.target_contract.decode_function_input(self.input)
            f_name = decode_result[0].fn_name
            f_args = decode_result[1]
            self.decoded = f"{f_name}({f_args})"
    def get_or_create_log(self, index=None, event=None, tx_hash = None, attributes={}):
        if index in self.logs.keys():
            lg = self.logs[index]
        else:
            lg = Log(event=event, attributes=dict(attributes))
            self.logs[index] = lg
        return lg


class Block:
    events = []
    number = 0
    timestamp = None
    def __init__(self, timestamp=None, number=0, hash=None):
        self.timestamp = timestamp
        self.number = number
        self.hash = hash
        self.txes = {}
    
    def get_or_create_tx(self, index=0, hash=None, to=None, input=None):
        if index in self.txes.keys():
            tx = self.txes[index]
        else:
            tx = Tx(hash=hash, to=to, input=input)
            self.txes[index] = tx
        return tx

class Pair:
    w3 = None
    router = None
    contract = None
    token0 = None
    token0_symbol = ""
    token0_reserve = 0
    token0_balance = 0
    token0_allowed = 0
    token1 = None
    token1_symbol = ""
    tx = None
    route = []
    spend_amount = 0
    rcv_amount = 0
    rcv_token_symbol = 0
    gas_price = 0
    blocks = {}

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
        self.token0_symbol = self.token0.functions.symbol().call()
        self.token1_symbol = self.token1.functions.symbol().call()
        self.name = f"{self.token0_symbol}_{self.token1_symbol}"

        print(f"Pair {self.name}")
        print(f"  Token0 {self.token0.functions.symbol().call()}")
        print(
            f"    price 1 {self.token0.functions.symbol().call()} = {self.router.functions.getAmountsOut(amountIn=int(1e18), path=[self.token0.address, self.token1.address]).call()[1]/1e18} {self.token1.functions.symbol().call()}"
        )
        print(f"    reserve {self.token0_reserve / 1e18}")
        print(f"  Token1 {self.token1.functions.symbol().call()}")
        print(
            f"    price 1 {self.token1.functions.symbol().call()} = {self.router.functions.getAmountsOut(amountIn=int(1e18), path=[self.token1.address, self.token0.address]).call()[1]/1e18} {self.token0.functions.symbol().call()}"
        )
        print(f"    reserve {self.token1_reserve / 1e18}")

    def get_token_by_symbol(self, symbol):
        if symbol == self.token0_symbol:
            return self.token0
        if symbol == self.token1_symbol:
            return self.token1
        return None
    
    def get_or_create_block(self, timestamp=0, number=0, hash=None):
        if number in self.blocks.keys():
            blk = self.blocks[number]
        else:
            blk = Block(timestamp=timestamp, number=number)
            self.blocks[number] = blk
        return blk

    
    def read_blocks(self, from_block, to_block):
        logs = self.contract.events.Mint.getLogs(fromBlock=from_block, toBlock=to_block)
        for i in logs:
            tx_det = w3.eth.getTransaction(i.transactionHash.hex())
            blk = self.get_or_create_block(number=tx_det.blockNumber)
            tx = blk.get_or_create_tx(index=tx_det.transactionIndex, hash=i.transactionHash.hex(), input=tx_det.input, to=tx_det.to)
            tx.decode()
            tx.get_or_create_log(index=i.logIndex, tx_hash = i.transactionHash.hex(), event=i.event, attributes=i.args)
        logs = self.contract.events.Swap.getLogs(fromBlock=from_block, toBlock=to_block)
        for i in logs:
            tx_det = w3.eth.getTransaction(i.transactionHash.hex())
            blk = self.get_or_create_block(number=tx_det.blockNumber)
            tx = blk.get_or_create_tx(index=tx_det.transactionIndex, hash=i.transactionHash.hex(), input=tx_det.input, to=tx_det.to)
            tx.decode()
            tx.get_or_create_log(index=i.logIndex, tx_hash = i.transactionHash.hex(), event=i.event, attributes=i.args)
        logs = self.contract.events.Burn.getLogs(fromBlock=from_block, toBlock=to_block)
        for i in logs:
            tx_det = w3.eth.getTransaction(i.transactionHash.hex())
            blk = self.get_or_create_block(number=tx_det.blockNumber)
            tx = blk.get_or_create_tx(index=tx_det.transactionIndex, hash=i.transactionHash.hex(), input=tx_det.input, to=tx_det.to)
            tx.decode()
            tx.get_or_create_log(index=i.logIndex, tx_hash = i.transactionHash.hex(), event=i.event, attributes=i.args)
        logs = self.contract.events.Sync.getLogs(fromBlock=from_block, toBlock=to_block)
        for i in logs:
            tx_det = w3.eth.getTransaction(i.transactionHash.hex())
            blk = self.get_or_create_block(number=tx_det.blockNumber)
            tx = blk.get_or_create_tx(index=tx_det.transactionIndex, hash=i.transactionHash.hex(), input=tx_det.input, to=tx_det.to)
            tx.decode()
            tx.get_or_create_log(index=i.logIndex, tx_hash = i.transactionHash.hex(), event=i.event, attributes=i.args)
    
    def print_blocks_and_txes(self):
        for blk_number in sorted(self.blocks.keys()):
            print(f"Block {blk_number}")
            for tx_id in sorted(self.blocks[blk_number].txes.keys()):
                print(f"  Tx {tx_id} {self.blocks[blk_number].txes[tx_id].hash}")
                print(f"    {self.blocks[blk_number].txes[tx_id].decoded}")
                for log_id in sorted(self.blocks[blk_number].txes[tx_id].logs.keys()):
                    lg = self.blocks[blk_number].txes[tx_id].logs[log_id]
                    print(f"      Log {log_id} {lg.event}({lg.attributes})")

p = Pair(w3)
p.set_pair(UNI_PAIR)
p.read_blocks(11900000, 11915157)
#p.read_blocks(11915120, 11915157)
p.print_blocks_and_txes()
