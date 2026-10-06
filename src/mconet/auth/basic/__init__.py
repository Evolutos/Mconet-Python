"""Built-in no-auth, API key, and bearer authorization module.

The S0 module intentionally exports no authorization behavior. Later work
packages implement only authorization-related domain and SPI contracts here,
without owning payload mapping or network transmission.
"""

__all__: tuple[str, ...] = ()
