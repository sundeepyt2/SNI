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

    Carries an actionable, human-readable ``hint`` describing how to recover.
    """

    def __init__(self, message: str = "Provider requires captcha.", hint: str = ""):
        self.hint = hint or (
            "All AllAnime API mirrors were captcha-walled. Two options:\n"
            "  1. Browser cookies from a working mirror (NOT allanime.day which\n"
            "     is broken with a redirect loop). Use allmanga.to or\n"
            "     allanime.uns.bio, then:\n"
            "       sni config --update allanime_cookies='cf_clearance=...;'\n"
            "  2. Deploy the XAN CF Worker and save URL:\n"
            "       sni config --update allanime_cf_worker_url='https://...'\n"
            "     Can't use Cloudflare? Deno Deploy / Vercel / Netlify also work.\n"
            "Run `sni config --cookie-info` for full step-by-step instructions."
        )
        super().__init__(f"{message}\n{self.hint}")


class ConfigError(SNIError):
    pass


class StreamError(SNIError):
    pass
