class ProviderUnavailable(Exception):
    pass

class ProviderStalled(Exception):
    """The model's response timed out or the connection dropped; trying again may work."""


class ContextLimitExceededError(Exception):
    def __init__(self, message="The input prompt exceeds the model's maximum context limit.", original_error=None):
        super().__init__(message)
        self.original_error = original_error

