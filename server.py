#!/usr/bin/env python3
"""Compatibility shim. The real package is netkit/.

This file exists so the original launch path (`python3 server.py` from the repo
root, used by the installed LaunchAgent) keeps working after the code moved into
the netkit package. New installs should use the `netkit` command or netkit.pyz.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from netkit.server import main

if __name__ == "__main__":
    main()
