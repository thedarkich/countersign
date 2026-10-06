"""Only disposable synthetic keys and temporary files are used in these tests."""

import importlib.util
import stat
from pathlib import Path

import pytest
from dotenv import dotenv_values
from eth_account import Account


@pytest.fixture
def helper(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/configure_wallets.py"
    spec = importlib.util.spec_from_file_location("wallet_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    accounts = [Account.create() for _ in range(4)]
    module.ROOT, module.ENV = tmp_path, tmp_path / "synthetic.env"
    module.EXPECTED = {
        name: account.address for name, account in zip(module.EXPECTED, accounts, strict=True)
    }
    monkeypatch.setattr(module.os, "isatty", lambda _: True)
    return module, accounts


def test_wallet_helper_validates_hides_keys_and_removes_duplicates(helper, monkeypatch, capsys):
    module, accounts = helper
    module.ENV.write_text(
        "KEEP=synthetic-other-value\nDEPLOYER_PK=bad\nexport 'DEPLOYER_PK'=bad2\n"
    )
    entries = iter(
        ["bad input", accounts[1].key.hex(), *[account.key.hex() for account in accounts]]
    )
    monkeypatch.setattr(module.getpass, "getpass", lambda _: next(entries))
    module.main()
    values = dotenv_values(module.ENV)
    output = capsys.readouterr().out
    assert values["KEEP"] == "synthetic-other-value"
    for name, account in zip(module.EXPECTED, accounts, strict=True):
        assert Account.from_key(values[name]).address == account.address
        assert module.ENV.read_text().count(name + "=") == 1
        assert account.key.hex() not in output
    assert stat.S_IMODE(module.ENV.stat().st_mode) == 0o600
    assert not list(module.ROOT.glob(".wallet-setup-*"))


def test_wallet_helper_cancel_is_all_or_nothing(helper, monkeypatch):
    module, accounts = helper
    original = "KEEP=unchanged\n"
    module.ENV.write_text(original)
    answers = iter([accounts[0].key.hex()])

    def input_key(_):
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr(module.getpass, "getpass", input_key)
    with pytest.raises(KeyboardInterrupt):
        module.main()
    assert module.ENV.read_text() == original
    assert not list(module.ROOT.glob(".wallet-setup-*"))


def test_wallet_helper_reuses_matching_keys_and_requires_terminal(helper, monkeypatch):
    module, accounts = helper
    module.ENV.write_text(
        "\n".join(
            name + "=" + account.key.hex()
            for name, account in zip(module.EXPECTED, accounts, strict=True)
        )
    )
    monkeypatch.setattr(
        module.getpass, "getpass", lambda _: pytest.fail("must not request known keys")
    )
    module.main()
    assert stat.S_IMODE(module.ENV.stat().st_mode) == 0o600
    monkeypatch.setattr(module.os, "isatty", lambda _: False)
    with pytest.raises(SystemExit, match="interactive"):
        module.main()
