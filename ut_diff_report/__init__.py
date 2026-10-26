"""Deterministic data validation and rendering; semantic analysis belongs to the Agent."""

__version__ = '0.7.1'
TEMPLATE_VERSION = '1.3.0'


def configure_cli():
    """Use a portable CLI wire encoding without changing callers that import the library."""
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
