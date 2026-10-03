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
import xbmcvfs

from nowplaying import ART_PROPERTY, VISUALISATION_WINDOW, show_view
from stations import STATIONS, status_url

# radio.co's status API answers 403 to Python's default urllib user-agent.
USER_AGENT = "Kodi/21.3 (plugin.audio.shirleyandspinoza)"

PLAY_PATH = "/play"

# Kodi builds a listing itself, and when that took it over a second it writes the result
# to special://temp/archive_cache/ and serves that copy from then on -- without calling
# the plugin again, and surviving an add-on reinstall. This listing is live: it carries
# the current track's artwork, so a copy of it is wrong the moment it is written.
LISTING_PATH = "plugin://plugin.audio.shirleyandspinoza"
CACHE_DIR = "special://temp/archive_cache/"


def cached_listing_suffix():
    """The tail of the name Kodi gives a cached copy of our listing: a window id, a dash,
    then the CRC32 of the lowercased path with its trailing slash stripped.

    Kodi computes that CRC32 itself (xbmc/utils/Crc32.cpp): polynomial 0x04C11DB7,
    initial value 0xFFFFFFFF, most significant bit first, and no final inversion. That is
    not zlib's crc32, so it is spelled out here rather than imported."""
    crc = 0xFFFFFFFF
    for byte in LISTING_PATH.lower().encode("utf-8"):
        crc ^= byte << 24
        for _ in range(8):
            crc = (
                ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                if crc & 0x80000000
                else (crc << 1) & 0xFFFFFFFF
            )
    return "-%08x.fi" % crc


def drop_cached_listing():
    """Delete the cached copy of the station listing, if Kodi made one.

    Called by the service at startup, and by the listing itself, so either running is
    enough to clear a device. An add-on update restarts the service inside the running
    session, and nothing else clears that cache: not a reinstall, and only a Kodi restart
    clears temp. So a device already carrying a stale copy would keep serving it, and the
    update would look like it changed nothing.
    """
    try:
        files = xbmcvfs.listdir(CACHE_DIR)[1]
    except Exception as error:
        xbmc.log("shirleyandspinoza: listing cache unreadable: %s" % error, xbmc.LOGWARNING)
        return
    suffix = cached_listing_suffix()
    found = [name for name in files if name.endswith(suffix)]
    for name in found:
        if not xbmcvfs.delete(CACHE_DIR + name):
            xbmc.log("shirleyandspinoza: could not drop %s" % name, xbmc.LOGWARNING)
    if found:
        xbmc.log("shirleyandspinoza: listing cache dropped %s" % found, xbmc.LOGINFO)
    else:
        xbmc.log("shirleyandspinoza: listing cache clean", xbmc.LOGDEBUG)


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
    playing = playing_station()
    # Kodi will serve a cached copy of this listing without calling the plugin at all, so a
    # stale copy from an older install can freeze the rows. Nothing should have written one
    # -- the listing declares itself uncacheable below -- so anything found here is stale.
    drop_cached_listing()
    if playing:
        # Already on air - this press is the way back to the now-playing screen.
        show_view(playing)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    xbmcplugin.setContent(handle, "songs")
    for station in STATIONS:
        item = xbmcgui.ListItem(label=station["name"], offscreen=True)
        item.setProperty("IsPlayable", "true")
        # Kodi's music info has no plot key -- setInfo("music", ...) logs and drops it -- so
        # the station's line goes on the video info tag, which is where Listitem.Plot reads
        # from. No media type goes with it, so the row stays a station, not a video.
        item.getVideoInfoTag().setPlot("%s\n%s" % (station["tagline"], station["site"]))
        artwork = current_artwork(station)
        if artwork:
            item.setArt({"thumb": artwork, "fanart": artwork, "poster": artwork})
        xbmc.log(
            "shirleyandspinoza: listing %s: art=%s" % (station["name"], artwork or "none"),
            xbmc.LOGINFO,
        )
        path = "%s%s?station=%s" % (base, PLAY_PATH, station["station_id"])
        xbmcplugin.addDirectoryItem(handle, path, item, isFolder=False)
    # Kodi must never keep a copy of this listing: the row carries the artwork of whatever
    # is playing now, so a cached copy is a frozen picture of an old track.
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


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
