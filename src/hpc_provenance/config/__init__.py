"""Configuration and composition root.

This package is the only one allowed to import from every other layer -- it
wires concrete ``infrastructure`` adapters into ``application`` use cases
based on ``Settings``.
"""
