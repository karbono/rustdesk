#!/usr/bin/env python3
"""Bake the homelab server into the client. Fails the build if upstream changed the
strings, instead of silently shipping a client that points at the public servers."""
import os
import sys

server = os.environ.get("RENDEZVOUS_SERVER") or "rd.lulospi.party"
key = os.environ.get("RS_PUB_KEY") or "ksulzKNoqGUqVDSrdFrZg9x7vyA9CWdYe0QttmYPtbQ="
api = os.environ.get("API_SERVER") or "https://rd.lulospi.party"

PATCHES = [
    ("libs/hbb_common/src/config.rs", '"rs-ny.rustdesk.com"', f'"{server}"'),
    ("libs/hbb_common/src/config.rs", '"OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw="', f'"{key}"'),
    ("src/common.rs", '"https://admin.rustdesk.com".to_owned()', f'"{api}".to_owned()'),
]
for path, old, new in PATCHES:
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if old in s:
        s = s.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"patched {path}: {old} -> {new}")
    elif new in s:
        print(f"already patched {path}: {new}")
    else:
        sys.exit(f"ERROR: {old} not found in {path}: upstream changed, update patch_custom_server.py")
