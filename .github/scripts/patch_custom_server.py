#!/usr/bin/env python3
"""Bake the homelab server into the client. Fails the build if upstream changed the
strings, instead of silently shipping a client that points at the public servers."""
import json
import os
import sys

server = os.environ.get("RENDEZVOUS_SERVER") or "rd.lulospi.party"
key = os.environ.get("RS_PUB_KEY") or "ksulzKNoqGUqVDSrdFrZg9x7vyA9CWdYe0QttmYPtbQ="
api = os.environ.get("API_SERVER") or "https://rd.lulospi.party"

# Settings baked into the client. OVERWRITE_SETTINGS wins over the user's own config and the UI
# shows them read-only (is_option_fixed), so nobody can point the client at the public servers.
# approve-mode "" = accept with the password OR with a click. No secrets here: the repo is public.
LOCKED = {
    "custom-rendezvous-server": server,
    "key": key,
    "api-server": api,
    "relay-server": server,
    "approve-mode": "",
}
# BUILTIN_SETTINGS: switches the Flutter UI reads (mainGetBuildinOption) to hide whole sections.
BUILTIN = {
    "hide-server-settings": "Y",
    "hide-network-settings": "Y",
}


def empty_map(name):
    return f"pub static ref {name}: RwLock<HashMap<String, String>> = Default::default();"


def rust_map(name, entries):
    pairs = ", ".join(f"({json.dumps(k)}.to_owned(), {json.dumps(v)}.to_owned())" for k, v in entries.items())
    return f"pub static ref {name}: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([{pairs}]));"


PATCHES = [
    ("libs/hbb_common/src/config.rs", '"rs-ny.rustdesk.com"', f'"{server}"'),
    ("libs/hbb_common/src/config.rs", '"OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw="', f'"{key}"'),
    ("src/common.rs", '"https://admin.rustdesk.com".to_owned()', f'"{api}".to_owned()'),
    ("libs/hbb_common/src/config.rs", empty_map("OVERWRITE_SETTINGS"), rust_map("OVERWRITE_SETTINGS", LOCKED)),
    ("libs/hbb_common/src/config.rs", empty_map("BUILTIN_SETTINGS"), rust_map("BUILTIN_SETTINGS", BUILTIN)),
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
