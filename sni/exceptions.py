class SNIError(Exception):
    pass


class ProviderError(SNIError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderHealthError(ProviderError):
    pass


class CaptchaRequiredError(ProviderError):
    """Raised when a provider (typically AllAnime) demands a captcha/cookies.

    Carries an actionable, human-readable ``hint`` describing how to obtain
    and supply browser cookies so the user can recover without reading docs.
    """

    def __init__(self, message: str = "Provider requires captcha.", hint: str = ""):
        self.hint = hint or (
            "AllAnime's edge blocked this request. Two fixes:\n"
            "  1. (Recommended) Deploy the XAN Cloudflare Worker and save its URL:\n"
            "       sni config --update allanime_cf_worker_url='https://your-worker.workers.dev'\n"
            "     The worker proxies requests through Cloudflare's own IPs, which\n"
            "     AllAnime rarely challenges. Works even on VPN/shared IPs.\n"
            "  2. Pass browser cookies:\n"
            "       sni config --update allanime_cookies='k1=v1; k2=v2'\n"
            "     (get the cookie string from DevTools -> Application -> Cookies on\n"
            "     https://allanime.day).\n"
            "Run `sni config --cookie-info` for full step-by-step instructions."
        )
        super().__init__(f"{message}\n{self.hint}")


class ConfigError(SNIError):
    pass


class StreamError(SNIError):
    pass
