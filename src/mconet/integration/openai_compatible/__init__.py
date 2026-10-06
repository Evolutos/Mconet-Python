"""R1 OpenAI-compatible text conversation integration module.

The S0 module intentionally exports no integration behavior. Later work
packages implement private protocol mapping against core-domain and core-spi;
core-domain and core-runtime must never depend on this concrete integration.
"""

__all__: tuple[str, ...] = ()
