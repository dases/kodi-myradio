"""plugin.audio.shirleyandspinoza - the plugin entry point.

One station, so this entry point is itself the playable item: it resolves to the stream
URL with the current artwork attached.
"""

import json
import sys
import urllib.request

import xbmc
import xbmcgui
import xbmcplugin

STREAM_URL = "https://s2.radio.co/sec5fa6199/listen"
STATUS_URL = "https://public.radio.co/stations/sec5fa6199/status"

# radio.co's status API answers 403 to Python's default urllib user-agent.
USER_AGENT = "Kodi/21.3 (plugin.audio.shirleyandspinoza)"


def current_artwork():
    request = urllib.request.Request(STATUS_URL, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        return payload["current_track"].get("artwork_url_large")
    except Exception as error:
        xbmc.log("shirleyandspinoza: art fetch failed: %s" % error, xbmc.LOGWARNING)
        return None


def main():
    handle = int(sys.argv[1])
    xbmc.log("shirleyandspinoza: plugin invoked", xbmc.LOGINFO)

    item = xbmcgui.ListItem(label="Shirley & Spinoza Radio", offscreen=True)
    item.setPath(STREAM_URL)
    item.setInfo("music", {"title": "Shirley & Spinoza Radio"})

    artwork = current_artwork()
    if artwork:
        item.setArt({"thumb": artwork, "fanart": artwork, "poster": artwork})
        xbmc.log("shirleyandspinoza: resolved with art %s" % artwork, xbmc.LOGINFO)

    xbmcplugin.setResolvedUrl(handle, True, item)


if __name__ == "__main__":
    main()
