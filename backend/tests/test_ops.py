import sqlite3
import stat

import pytest

from app.ops import backup


def test_online_backup_includes_wal_and_does_not_overwrite(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "private-backup.db"
    with sqlite3.connect(source) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("CREATE TABLE records (value TEXT)")
        database.execute("INSERT INTO records VALUES ('synthetic invoice')")
        database.commit()
        backup(source, target)
        with sqlite3.connect(target) as restored:
            assert restored.execute("SELECT value FROM records").fetchone() == (
                "synthetic invoice",
            )
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
        with pytest.raises(FileExistsError):
            backup(source, target)


def test_missing_database_is_not_created_during_backup(tmp_path):
    with pytest.raises(ValueError):
        backup(tmp_path / "missing.db", tmp_path / "backup.db")
    assert not (tmp_path / "missing.db").exists()
