"""plugin.audio.shirleyandspinoza - the plugin entry point.

Two requests arrive here:

    plugin://plugin.audio.shirleyandspinoza/                   the station listing
    plugin://plugin.audio.shirleyandspinoza/play?station=<id>  the station, playable

The station resolves lazily on /play, so the artwork is fetched when the item is played
rather than when the folder is opened. Opening the addon while the station is already
playing is the way back to the now-playing screen, so that press jumps to the fullscreen
view instead of resolving a second stream.
"""

import json
import sys
import urllib.request
from urllib.parse import parse_qs, urlsplit

import xbmc
import xbmcgui
import xbmcplugin

from nowplaying import ART_PROPERTY, VISUALISATION_WINDOW, show_view
from stations import STATIONS, status_url

# radio.co's status API answers 403 to Python's default urllib user-agent.
USER_AGENT = "Kodi/21.3 (plugin.audio.shirleyandspinoza)"

PLAY_PATH = "/play"


def current_artwork(station):
    """The station's current artwork, falling back to the last image that reached the
    now-playing screen: a failed poll must not blank what is already there."""
    request = urllib.request.Request(status_url(station), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        artwork = payload["current_track"].get("artwork_url_large")
    except Exception as error:
        xbmc.log("shirleyandspinoza: art fetch failed: %s" % error, xbmc.LOGWARNING)
        artwork = None
    if artwork:
        return artwork
    return xbmcgui.Window(VISUALISATION_WINDOW).getProperty(ART_PROPERTY) or None


def playing_station():
    """The station the player is on, if it is playing one of ours."""
    player = xbmc.Player()
    if not player.isPlaying():
        return None
    playing_file = player.getPlayingFile()
    for station in STATIONS:
        if station["stream"] == playing_file:
            return station
    return None


def station_listing(handle, base):
    """The station folder: one playable row per station."""
    if playing_station():
        # Already on air - this press is the way back to the now-playing screen.
        show_view()
        xbmcplugin.endOfDirectory(handle)
        return

    xbmcplugin.setContent(handle, "songs")
    for station in STATIONS:
        item = xbmcgui.ListItem(label=station["name"], offscreen=True)
        item.setProperty("IsPlayable", "true")
        artwork = current_artwork(station)
        if artwork:
            item.setArt({"thumb": artwork, "fanart": artwork, "poster": artwork})
        path = "%s%s?station=%s" % (base, PLAY_PATH, station["station_id"])
        xbmcplugin.addDirectoryItem(handle, path, item, isFolder=False)
    xbmcplugin.endOfDirectory(handle)


def play(handle, station):
    """Resolve the station to its stream URL, with the current artwork attached."""
    item = xbmcgui.ListItem(label=station["name"], offscreen=True)
    item.setPath(station["stream"])
    item.setInfo("music", {"title": station["name"]})

    artwork = current_artwork(station)
    if artwork:
        item.setArt({"thumb": artwork, "fanart": artwork, "poster": artwork})
        xbmc.log("shirleyandspinoza: resolved with art %s" % artwork, xbmc.LOGINFO)

    xbmcplugin.setResolvedUrl(handle, True, item)


def main():
    handle = int(sys.argv[1])
    # argv[0] carries the URL's path; argv[2] carries its query string, if any.
    parsed = urlsplit(sys.argv[0])
    base = "%s://%s" % (parsed.scheme, parsed.netloc)
    path = parsed.path or "/"
    query = urlsplit(sys.argv[2] if len(sys.argv) > 2 else "").query
    station_id = parse_qs(query).get("station", [None])[0]
    xbmc.log("shirleyandspinoza: plugin invoked %s (station=%s)" % (path, station_id), xbmc.LOGINFO)

    if path == PLAY_PATH:
        station = next((s for s in STATIONS if s["station_id"] == station_id), STATIONS[0])
        play(handle, station)
    else:
        station_listing(handle, base)


if __name__ == "__main__":
    main()
