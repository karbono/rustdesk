#!/usr/bin/env python3
"""Invariants of the custom-build workflows (stdlib unittest + PyYAML).

    python3 .github/tests/test_custom_workflows.py

- flutter-build.yml only patches/verifies the homelab server when the caller sets custom-client,
  and only build-custom.yml does.
- Release uploads are fatal (no continue-on-error), so fixed-name-downloads never republishes
  assets from an older run.
- fixed-name-downloads checks the ABIs the APK really ships, and fails on none or a bad one.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WF = os.path.join(ROOT, ".github", "workflows")


def load(name):
    with open(os.path.join(WF, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def steps(wf):
    for job_name, job in wf["jobs"].items():
        for step in job.get("steps", []) or []:
            yield job_name, step


def on(wf):
    # PyYAML (YAML 1.1) reads the bare key `on` as True.
    return wf.get("on", wf.get(True))


def fixed_name_script():
    wf = load("build-custom.yml")
    return wf["jobs"]["fixed-name-downloads"]["steps"][0]["run"]


class CustomClientGate(unittest.TestCase):
    def test_input_defaults_to_false(self):
        inp = on(load("flutter-build.yml"))["workflow_call"]["inputs"]["custom-client"]
        self.assertEqual(inp["type"], "boolean")
        self.assertIs(inp["default"], False)

    def test_every_custom_step_is_gated(self):
        found = 0
        for job, step in steps(load("flutter-build.yml")):
            run = step.get("run", "") or ""
            if "patch_custom_server.py" in run or "verify_custom_server.py" in run:
                found += 1
                self.assertIn("inputs.custom-client", str(step.get("if", "")), f"{job}: {step.get('name')}")
        self.assertGreater(found, 0)

    def test_only_build_custom_sets_it(self):
        for name in sorted(os.listdir(WF)):
            if not name.endswith((".yml", ".yaml")):
                continue
            for job_name, job in (load(name).get("jobs") or {}).items():
                if not str(job.get("uses", "")).endswith("flutter-build.yml"):
                    continue
                value = (job.get("with") or {}).get("custom-client", False)
                if name == "build-custom.yml":
                    self.assertIs(value, True)
                else:
                    self.assertIs(value, False, f"{name}:{job_name}")


class ReleaseUploadIsFatal(unittest.TestCase):
    def test_no_continue_on_error_on_release_upload(self):
        for name in ("flutter-build.yml", "build-custom.yml"):
            for job, step in steps(load(name)):
                if "action-gh-release" in str(step.get("uses", "")) or "gh release upload" in str(step.get("run", "")):
                    self.assertFalse(step.get("continue-on-error", False), f"{name}:{job}: {step.get('name')}")


@unittest.skipUnless(shutil.which("unzip") and shutil.which("bash"), "needs bash and unzip")
class ApkAbiCheck(unittest.TestCase):
    """Runs the real fixed-name-downloads script against fake release assets with a stub gh."""

    GOOD = b"rd.karbono.es hide-server-settings"
    BAD = b"rs-ny.rustdesk.com"

    def run_script(self, libs, tmp=None):
        if tmp is None:
            tmp = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, tmp)
        assets, binp = os.path.join(tmp, "assets"), os.path.join(tmp, "bin")
        os.makedirs(assets)
        os.makedirs(binp)
        for f in ("rustdesk-1.5.3-x86_64.exe", "rustdesk-1.5.3-x86_64.msi"):
            with open(os.path.join(assets, f), "wb") as fh:
                fh.write(b"x")
        with zipfile.ZipFile(os.path.join(assets, "rustdesk-1.5.3-universal.apk"), "w") as z:
            z.writestr("AndroidManifest.xml", "x")
            for abi, data in libs.items():
                z.writestr(f"lib/{abi}/librustdesk.so", data)
        gh = os.path.join(binp, "gh")
        with open(gh, "w") as fh:
            fh.write(
                '#!/bin/sh\n'
                'if [ "$2" = download ]; then cp "$ASSETS"/* .; '
                'elif [ "$2" = upload ]; then printf "%s\\n" "$@" > "$UPLOAD_LOG"; fi\n'
                'exit 0\n'
            )
        os.chmod(gh, 0o755)
        env = dict(os.environ, PATH=binp + os.pathsep + os.environ["PATH"], ASSETS=assets, TAG="custom",
                   UPLOAD_LOG=os.path.join(tmp, "gh_upload_args.txt"),
                   GITHUB_STEP_SUMMARY=os.path.join(tmp, "summary"))
        return subprocess.run(["bash", "-c", fixed_name_script()], cwd=tmp, env=env, capture_output=True, text=True)

    def test_missing_abi_is_fine(self):
        r = self.run_script({"arm64-v8a": self.GOOD, "x86_64": self.GOOD})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_publishes_rustdesk_soporte_names(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        r = self.run_script({"arm64-v8a": self.GOOD, "x86_64": self.GOOD}, tmp=tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        dl_dir = os.path.join(tmp, "dl")
        dl_files = sorted(os.listdir(dl_dir))
        for expected in (
            "rustdesk-soporte.exe",
            "rustdesk-soporte.msi",
            "rustdesk-soporte.apk",
            "rustdesk-soporte-SHA256SUMS.txt",
            "rustdesk-soporte-VERSION.txt",
        ):
            self.assertIn(expected, dl_files)
        self.assertFalse(any(f.startswith(("rustdesk-lulos.", "rustdesk-lulos-", "rustdesk-lulospi-")) for f in dl_files), dl_files)
        with open(os.path.join(dl_dir, "rustdesk-soporte-SHA256SUMS.txt"), encoding="utf-8") as fh:
            sums = fh.read()
        for expected in ("rustdesk-soporte.exe", "rustdesk-soporte.msi", "rustdesk-soporte.apk"):
            self.assertIn(expected, sums)
        self.assertNotIn("rustdesk-lulos", sums)
        self.assertNotIn("rustdesk-soporte-SHA256SUMS.txt", sums)
        self.assertNotIn("rustdesk-soporte-VERSION.txt", sums)
        with open(os.path.join(tmp, "gh_upload_args.txt"), encoding="utf-8") as fh:
            upload_args = fh.read().splitlines()
        for expected in (
            "rustdesk-soporte.exe",
            "rustdesk-soporte.msi",
            "rustdesk-soporte.apk",
            "rustdesk-soporte-SHA256SUMS.txt",
            "rustdesk-soporte-VERSION.txt",
        ):
            self.assertIn(expected, upload_args)
        self.assertFalse(any(a.startswith(("rustdesk-lulos.", "rustdesk-lulos-", "rustdesk-lulospi-")) for a in upload_args), upload_args)

    def test_bad_present_abi_fails(self):
        r = self.run_script({"arm64-v8a": self.GOOD, "armeabi-v7a": self.BAD})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("armeabi-v7a", r.stdout)

    def test_no_abi_fails(self):
        r = self.run_script({})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no lib/<abi>/librustdesk.so", r.stdout)


@unittest.skipUnless(shutil.which("shellcheck"), "needs shellcheck")
class ShellCheck(unittest.TestCase):
    def test_fixed_name_script(self):
        r = subprocess.run(["shellcheck", "-s", "bash", "-S", "warning", "-"], input=fixed_name_script(),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
