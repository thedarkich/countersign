import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from eth_utils import to_checksum_address
from web3 import HTTPProvider, Web3
from web3.middleware import ExtraDataToPOAMiddleware

from app.chain.errors import ChainSendError
from app.chain.tx_writer import TransactionWriter
from app.pipeline.match import PurchaseOrder, Vendor
from app.pipeline.runner import RegistrySnapshot

ABI = json.loads((Path(__file__).parent / "abi" / "Countersign.json").read_text())
ZERO = "0x" + "00" * 20
TOKEN_ABI = [
    {
        "type": "function",
        "name": name,
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": kind}],
    }
    for name, kind in (("decimals", "uint8"), ("symbol", "string"))
]


@dataclass
class NetworkClient:
    w3: Web3
    contract: object
    chain_id: int
    explorer_url: str


class VaultClient:
    def __init__(
        self,
        networks: dict[str, NetworkClient],
        addresses: dict[str, str],
        private_keys: dict[str, str],
        data_dir: Path,
        *,
        transactions_enabled=False,
        engine=None,
    ):
        self.networks, self.addresses = networks, addresses
        self.vendor_names = json.loads((data_dir / "vendors.json").read_text())
        self.po_names = json.loads((data_dir / "pos.json").read_text())
        self.writers = {
            (network, agent): TransactionWriter(
                client.w3,
                client.contract,
                chain_id=client.chain_id,
                network=network,
                explorer_url=client.explorer_url,
                expected_address=address,
                private_key=private_keys.get(agent, ""),
                enabled=transactions_enabled,
                engine=engine,
            )
            for network, client in networks.items()
            for agent, address in addresses.items()
        }

    @classmethod
    def from_settings(cls, settings, *, engine=None):
        networks = {}
        for name, chain_id in (("mainnet", 677), ("testnet", 968)):
            address = getattr(settings, "contract_address_" + name)
            if not address:
                continue
            provider = HTTPProvider(
                getattr(settings, "botchain_" + name + "_rpc"),
                request_kwargs={"timeout": 10},
                exception_retry_configuration=None,
            )
            w3 = Web3(provider)
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            contract = w3.eth.contract(address=to_checksum_address(address), abi=ABI)
            networks[name] = NetworkClient(
                w3, contract, chain_id, getattr(settings, "explorer_url_" + name)
            )
        addresses = {
            "guarded": settings.agent_guarded_address,
            "naive": settings.agent_naive_address,
        }
        keys = {
            "guarded": settings.agent_guarded_pk.get_secret_value(),
            "naive": settings.agent_naive_pk.get_secret_value(),
        }
        return cls(
            networks,
            addresses,
            keys,
            settings.data_dir,
            transactions_enabled=settings.transactions_enabled,
            engine=engine,
        )

    def _client(self, network):
        client = self.networks.get(network)
        if client is None or client.w3.eth.chain_id != client.chain_id:
            raise ChainSendError("Network is not configured or chain ID differs")
        return client

    def _snapshot(self, network: str) -> RegistrySnapshot:
        client = self._client(network)
        w3, contract = client.w3, client.contract
        block = w3.eth.block_number
        if not w3.eth.get_code(contract.address, block_identifier=block):
            raise ChainSendError("Configured vault has no bytecode")

        def read(name, *args):
            return getattr(contract.functions, name)(*args).call(
                block_identifier=block, ccip_read_enabled=False
            )

        vendors = []
        for item in self.vendor_names:
            payout, _active, exists = read("vendors", item["id"])
            if exists:
                vendors.append(
                    Vendor(
                        item["id"], item["name_en"], item["name_zh"], tuple(item["aliases"]), payout
                    )
                )
        pos = []
        for item in self.po_names:
            record = read("pos", item["po_id"])
            if record[6]:
                pos.append(
                    PurchaseOrder(
                        item["po_id"], item["ref"], record[0], read("poRemaining", item["po_id"])
                    )
                )
        asset = read("token")
        decimals, symbol = 18, "BOT"
        if asset.lower() != ZERO:
            token = w3.eth.contract(address=asset, abi=TOKEN_ABI)
            decimals = token.functions.decimals().call(
                block_identifier=block, ccip_read_enabled=False
            )
            symbol = token.functions.symbol().call(block_identifier=block, ccip_read_enabled=False)
        if not 0 <= decimals <= 77 or not symbol:
            raise ChainSendError("Unsupported vault asset metadata")
        return RegistrySnapshot(
            client.chain_id, contract.address, dict(self.addresses), vendors, pos, decimals, symbol
        )

    async def snapshot(self, network: str) -> RegistrySnapshot:
        return await asyncio.to_thread(self._snapshot, network)

    async def invoice_paid(self, network: str, invoice_hash: str) -> bool:
        def read():
            client = self._client(network)
            return client.contract.functions.invoicePaid(invoice_hash).call(ccip_read_enabled=False)

        return await asyncio.to_thread(read)

    async def send(self, network, agent, proposal, on_broadcast):
        writer = self.writers.get((network, agent))
        if writer is None:
            raise ChainSendError("Agent or network is not configured")
        return await asyncio.to_thread(writer.send, proposal, on_broadcast)
