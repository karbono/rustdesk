#!/usr/bin/env python3
"""Bake the homelab server into the client. Fails the build if upstream changed the
strings, instead of silently shipping a client that points at the public servers."""
import base64
import hashlib
import json
import os
import secrets
import sys

server = os.environ.get("RENDEZVOUS_SERVER") or "rd.lulospi.party"
key = os.environ.get("RS_PUB_KEY") or "ksulzKNoqGUqVDSrdFrZg9x7vyA9CWdYe0QttmYPtbQ="
api = os.environ.get("API_SERVER") or "https://rd.lulospi.party"

# Settings baked into the client. OVERWRITE_SETTINGS wins over the user's own config and the UI
# shows them read-only (is_option_fixed), so nobody can point the client at the public servers.
# Only the shared permanent password lets anyone in: no temporary password, no click-to-accept.
LOCKED = {
    "custom-rendezvous-server": server,
    "key": key,
    "api-server": api,
    "relay-server": server,
    "approve-mode": "password",
    "verification-method": "use-permanent-password",
}
# BUILTIN_SETTINGS: switches the Flutter UI reads (mainGetBuildinOption) to hide whole sections.
BUILTIN = {
    "hide-server-settings": "Y",
    "hide-network-settings": "Y",
    "disable-change-permanent-password": "Y",
}
# OVERWRITE_DISPLAY_SETTINGS: what a new remote session starts with (scale to the window, muted).
DISPLAY = {
    "view_style": "adaptive",
    "disable_audio": "Y",
}

# Shared permanent password, from the RUSTDESK_PRESET_PASSWORD Actions secret. Only its salted hash
# goes into the binary, in the format hbb_common expects for a preset password: HARD_SETTINGS
# "password" = "00" + base64(sha256(password + salt)), "salt" = salt (must not be empty, or the
# value is taken as plaintext). Without the secret the client would accept nobody, so fail instead.
password = os.environ.get("RUSTDESK_PRESET_PASSWORD", "")
if not password:
    sys.exit("ERROR: RUSTDESK_PRESET_PASSWORD secret is empty: a password-only client could never be reached")
if len(password) > 127:
    sys.exit("ERROR: RUSTDESK_PRESET_PASSWORD is longer than RustDesk accepts")
salt = secrets.token_urlsafe(24)
h1 = hashlib.sha256(password.encode() + salt.encode()).digest()
HARD = {
    "password": "00" + base64.b64encode(h1).decode(),
    "salt": salt,
}
del password


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
    ("libs/hbb_common/src/config.rs", empty_map("OVERWRITE_DISPLAY_SETTINGS"), rust_map("OVERWRITE_DISPLAY_SETTINGS", DISPLAY)),
    ("libs/hbb_common/src/config.rs", empty_map("HARD_SETTINGS"), rust_map("HARD_SETTINGS", HARD)),
]
for path, old, new in PATCHES:
    with open(path, encoding="utf-8") as f:
        s = f.read()
    if old in s:
        s = s.replace(old, new)
        with open(path, "w", encoding="utf-8") as f:
            f.write(s)
        print(f"patched {path}: {old[:60]}")
    elif new in s:
        print(f"already patched {path}")
    else:
        sys.exit(f"ERROR: {old} not found in {path}: upstream changed, update patch_custom_server.py")
