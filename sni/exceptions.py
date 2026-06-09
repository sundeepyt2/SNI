class SNIError(Exception):
    pass


class ProviderError(SNIError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderHealthError(ProviderError):
    pass


class ConfigError(SNIError):
    pass


class StreamError(SNIError):
    pass
