# Shirley & Spinoza Radio for Kodi

[Kodi](https://kodi.tv/) add-on to play your favourite internet radio station ([Shirley & Spinoza](https://www.shirleyandspinoza.radio/)) on TV!

When you wonder about sonic nugget, no need to rush to unlock phone or find tab, just look at TV!

Your whole family will be grateful for finally good use for Xbox TV!

## Install

Tested on Kodi 21 (Xbox and Desktop).

1. **Settings → File manager → Add source**
2. Enter the source URL in the *path* field:

   ```
   https://dases.github.io/kodi-shirleyandspinoza/dist/
   ```

   Use *Add source*, not *Add network location* — the latter offers ftp/rss/nfs and cannot
   express a plain HTTP URL.
3. **Settings → System → Add-ons → enable "Unknown sources"**
4. **Settings → Add-ons → Install from zip file** → pick the new source → pick the newest
   `plugin.audio.shirleyandspinoza-<version>.zip`
5. Kodi lists the add-on as disabled. Enable it.

### Updating

Install the newer zip the same way. The add-on id (`plugin.audio.shirleyandspinoza`) does
not change between releases, so the new build overwrites the old one in place — no
uninstall first. Only an id change would force one.

