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
            "AllAnime's edge blocked this request. Try in order:\n"
            "  1. (Fastest) Switch provider: sni play 'X' -p hianime\n"
            "  2. (If you must use allanime) Get cookies from a working mirror\n"
            "     (https://allmanga.to or https://allanime.uns.bio — NOT\n"
            "     allanime.day which is currently broken with a redirect loop)\n"
            "     and save them:\n"
            "       sni config --update allanime_cookies='cf_clearance=...;'\n"
            "  3. (VPN/shared IPs only) Deploy the XAN CF Worker and save URL:\n"
            "       sni config --update allanime_cf_worker_url='https://...'\n"
            "     Can't use Cloudflare? Deno Deploy / Vercel / Netlify also work.\n"
            "Run `sni config --cookie-info` for full step-by-step instructions."
        )
        super().__init__(f"{message}\n{self.hint}")


class ConfigError(SNIError):
    pass


class StreamError(SNIError):
    pass
