"""SNI exceptions — clean, actionable error messages."""


class SNIError(Exception):
    """Base class for all SNI errors."""


class SearchError(SNIError):
    """Search failed."""


class StreamError(SNIError):
    """Stream extraction or playback failed."""


class PlayerError(SNIError):
    """Player (mpv) error."""


class ConfigError(SNIError):
    """Configuration error."""
