import re
import unicodedata
from decimal import Decimal, InvalidOperation

from eth_abi import encode
from eth_utils import keccak

UINT256_MAX = 2**256 - 1


def normalize_invoice_number(value: str) -> str:
    return re.sub(r"[\s\-_/#]", "", unicodedata.normalize("NFKC", value).upper())


def normalize_po_reference(value: str) -> str:
    return re.sub(r"[\s\-_]", "", unicodedata.normalize("NFKC", value).upper())


def invoice_hash(vendor_id: int, invoice_number: str) -> str:
    normalized = normalize_invoice_number(invoice_number)
    if not 0 <= vendor_id <= UINT256_MAX or not normalized or len(normalized) > 200:
        raise ValueError("invalid invoice identity")
    return "0x" + keccak(encode(["uint256", "string"], [vendor_id, normalized])).hex()


def to_base_units(value: str | float | Decimal, decimals: int) -> int:
    if not 0 <= decimals <= 77:
        raise ValueError("unsupported token precision")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0:
            raise ValueError("amount must be finite and positive")
        # Integer arithmetic avoids the Decimal context's default precision limit.
        _, digits, exponent = amount.as_tuple()
        coefficient = int("".join(map(str, digits)))
        shift = int(exponent) + decimals
        if shift >= 0:
            if len(digits) + shift > 78:
                raise ValueError("amount exceeds uint256")
            result = coefficient * 10**shift
        else:
            if -shift > len(digits):
                raise ValueError("amount exceeds token precision")
            result, remainder = divmod(coefficient, 10 ** (-shift))
            if remainder:
                raise ValueError("amount exceeds token precision")
        if result > UINT256_MAX:
            raise ValueError("amount exceeds uint256")
        return result
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError("invalid amount") from exc
