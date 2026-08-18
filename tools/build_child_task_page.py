#!/usr/bin/env python3
"""Compatibility entrypoint for rebuilding C-2308 static task evidence data.

The child page is now modular source code and is no longer generated from the
P-1047 HTML. This command remains so existing local workflows keep working.
"""

from generate_demo_details import generate_attention


if __name__ == "__main__":
    generate_attention()
    print("Rebuilt C-2308 attention detail data; the modular page was unchanged")
