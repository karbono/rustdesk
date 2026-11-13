#!/usr/bin/env python3
"""Check that a built binary carries the homelab server and not the public one.

    verify_custom_server.py FILE [FILE...]

Works on the uncompressed library (librustdesk.dll / librustdesk.so), not on packed installers."""
import os
import sys

server = (os.environ.get("RENDEZVOUS_SERVER") or "rd.lulospi.party").encode()
key = (os.environ.get("RS_PUB_KEY") or "ksulzKNoqGUqVDSrdFrZg9x7vyA9CWdYe0QttmYPtbQ=").encode()
PUBLIC = [b"rs-ny.rustdesk.com", b"OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw="]
# Only reaches the Rust library through patch_custom_server.py: proves the settings lock is in.
LOCK_MARKER = b"hide-server-settings"

if len(sys.argv) < 2:
    sys.exit("usage: verify_custom_server.py FILE [FILE...]")
bad = False
for path in sys.argv[1:]:
    with open(path, "rb") as f:
        data = f.read()
    problems = [f"missing {w.decode()}" for w in (server, key, LOCK_MARKER) if w not in data] + [f"still has {w.decode()}" for w in PUBLIC if w in data]
    print(f"{path}: {'OK' if not problems else '; '.join(problems)}")
    bad = bad or bool(problems)
if bad:
    sys.exit("ERROR: this build does not point at the homelab server")
