# Custom build (homelab)

`Actions → Build Custom RustDesk (Windows & Android) → Run workflow` builds Windows x64 and Android with the
homelab server baked in, and publishes them in the `custom` release.

- Server, key and API come from the secrets `RENDEZVOUS_SERVER`, `RS_PUB_KEY`, `API_SERVER`, or the defaults in
  `.github/scripts/patch_custom_server.py`. If upstream renames the strings the script patches, the build fails
  instead of shipping a client that points at the public servers. `verify_custom_server.py` then checks the built
  Windows library, and the fixed-name step checks the APK and the deb.
- After the build, `fixed-name-downloads` copies the newest files to names that never change
  (`rustdesk-lulospi-windows.exe`, `rustdesk-lulospi-windows.msi`, `rustdesk-lulospi-android.apk`) and checks that the
  APK really contains the homelab server. `https://dl.lulospi.party/win` and `/android` redirect to those.
  Run the workflow with `only_links` ticked to refresh them without building (about a minute).
- Android signing: with the secrets `ANDROID_SIGNING_KEY` (base64 keystore), `ANDROID_ALIAS`,
  `ANDROID_KEY_STORE_PASSWORD` and `ANDROID_KEY_PASSWORD` every build is signed with the same key, so a new APK
  installs over the old one. Without them each build gets a throwaway debug key and Android refuses the update.
- The Windows exe is not code-signed: SmartScreen shows "unknown publisher" (More info → Run anyway).
- Built: Windows x64, Android, and Linux x86_64 (deb, rpm, Arch package, AppImage). The AppImage is the one behind
  `https://dl.lulospi.party/linux`. Everything else (macOS, iOS, ARM, web) is switched off. The nightly schedule is off.
