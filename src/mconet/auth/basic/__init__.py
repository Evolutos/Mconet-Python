"""Built-in no-auth, API key, and bearer authorization module.

No-authorization and header API key decisions are defined here. Bearer
authorization remains a separate implementation.
"""

from mconet.auth.basic.api_key_header_authorization import (
    API_KEY_HEADER_AUTHORIZATION_KIND,
    ApiKeyHeaderAuthorization,
)
from mconet.auth.basic.no_authorization import (
    NO_AUTHORIZATION_KIND,
    NoAuthorization,
)

__all__: tuple[str, ...] = (
    "API_KEY_HEADER_AUTHORIZATION_KIND",
    "NO_AUTHORIZATION_KIND",
    "ApiKeyHeaderAuthorization",
    "NoAuthorization",
)
