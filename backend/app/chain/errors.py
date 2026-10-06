class ChainSendError(RuntimeError):
    """Sanitized error with a public hash for later receipt reconciliation."""

    def __init__(self, message: str, tx_hash: str | None = None):
        super().__init__(message)
        self.tx_hash = tx_hash
