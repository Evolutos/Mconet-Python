"""Default HTTP transport backed by Python platform networking.

The S0 module intentionally exports no transport behavior. Later work packages
implement core SPI transport contracts without importing tasks, messages,
protocol adapters, or authorization behavior.
"""

__all__: tuple[str, ...] = ()
