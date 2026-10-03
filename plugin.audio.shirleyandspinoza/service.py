"""plugin.audio.shirleyandspinoza - the background service.

Estuary's MusicVisualisation.xml draws its fullscreen background from the visualisation
window's own property:

    <texture background="true">$INFO[Window(Visualisation).Property(ArtistSlideshow.Image)]</texture>

That property is the live-artwork hook: Player.updateInfoTag() was measured NOT to move
Player.Art(fanart) for the playing item, so it cannot swap the background, but setting
this window property can. This service opens the visualisation window when the station
starts, republishes radio.co's current artwork onto it as tracks change, and puts the
stream back when it drops.

Kodi dispatches a service's callbacks on the thread waiting in waitForAbort(), so the
callbacks here only record what happened; the polling and the reconnect attempts run on
the worker thread this module starts.
"""

import json
import threading
import time
import urllib.request

import xbmc
import xbmcgui

from addon import drop_cached_listing
from nowplaying import (
    ART_PROPERTY,
    VISUALISATION_WINDOW,
    bar_open,
    clear_art,
    close_bar,
    leave_view,
    show_view,
)
from stations import STATIONS, status_url

POLL_SECONDS = 15
RECONNECT_SECONDS = 5
GIVE_UP_AFTER = 30

# Kodi fires OnAVStarted for an attempt that then fails to open, in about a tenth of a
# second. Only a stream that outlives that counts as playing, and so as having dropped.
PLAYED_LONG_ENOUGH = 1.0

# radio.co's status API answers 403 to Python's default urllib user-agent.
USER_AGENT = "Kodi/21.3 (plugin.audio.shirleyandspinoza)"

IDLE = "idle"
PLAYING = "playing"
RECONNECTING = "reconnecting"


def station_for(playing_file):
    for station in STATIONS:
        if station["stream"] == playing_file:
            return station
    return None


def fetch_artwork(station):
    """The station's current artwork, or None if the status API will not say."""
    request = urllib.request.Request(status_url(station), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
        return payload["current_track"].get("artwork_url_large")
    except Exception as error:
        xbmc.log("shirleyandspinoza: status fetch failed: %s" % error, xbmc.LOGWARNING)
        return None


class StationService(xbmc.Player):
    def __init__(self):
        self.state = IDLE
        self.station = None
        self.last_poll = 0.0
        self.playing_since = 0.0
        self.view_shown = False
        self.next_attempt = 0.0
        self.retry_until = 0.0
        self.ended = False
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self.run)
        self.worker.daemon = True
        self.worker.start()

    def onAVStarted(self):
        # Kodi fires the AV callbacks even when it has already given up on the item
        # (a stream that dies as it opens), and getPlayingFile() raises then.
        try:
            playing = self.getPlayingFile()
        except RuntimeError:
            return
        station = station_for(playing)
        if not station:
            return
        # The view and the first artwork wait for the worker to see this attempt still
        # playing: OnAVStarted alone does not mean the stream opened.
        with self.lock:
            self.station = station
            self.state = PLAYING
            self.playing_since = time.time()
            self.view_shown = False
            self.ended = False

    def onPlayBackEnded(self):
        self.stream_died()

    def onPlayBackError(self):
        self.stream_died()

    def onPlayBackStopped(self):
        with self.lock:
            died = self.ended
            self.ended = False
            if not died:
                # A stop someone asked for: the station stays off, and our bar goes with it.
                self.state = IDLE
        if not died:
            close_bar()
            clear_art()

    def stream_died(self):
        """The stream ended or errored. A reconnect attempt of ours that fails to open
        fires the same callbacks, so only a stream that had really been playing may
        (re)start the give-up clock."""
        with self.lock:
            self.ended = True
            if self.state == PLAYING:
                self.state = RECONNECTING
                # An attempt that fails to open dies in about a tenth of a second; one
                # that outlives PLAYED_LONG_ENOUGH was a stream, and its death is the
                # drop the clock runs from. With no clock running, start one.
                was_a_stream = time.time() - self.playing_since >= PLAYED_LONG_ENOUGH
                if was_a_stream or time.time() > self.retry_until:
                    self.retry_until = time.time() + GIVE_UP_AFTER
                    self.next_attempt = 0.0

    def run(self):
        monitor = xbmc.Monitor()
        while not monitor.abortRequested():
            try:
                with self.lock:
                    state, station = self.state, self.station
                if state == PLAYING:
                    if not self.view_shown:
                        if self.isPlaying():
                            with self.lock:
                                self.view_shown = True
                            show_view(station)
                            self.last_poll = time.time()
                            self.refresh_artwork(station)
                    else:
                        self.hide_skin_bar()
                        if time.time() - self.last_poll >= POLL_SECONDS:
                            self.last_poll = time.time()
                            self.refresh_artwork(station)
                elif state == RECONNECTING:
                    self.reconnect(station)
            except Exception as error:
                xbmc.log("shirleyandspinoza: service tick failed: %s" % error, xbmc.LOGERROR)
            if monitor.waitForAbort(1):
                return

    def hide_skin_bar(self):
        """The skin's own track panel shows itself for a few seconds at every track change,
        drawn where ours is. Ours is the one that should be seen, so dismiss the skin's as
        soon as it appears."""
        if not bar_open():
            return
        if xbmc.getCondVisibility("Player.ShowInfo"):
            xbmc.executebuiltin("Action(Info)")
        # The Info action does not always toggle the panel off. When the skin has just
        # raised its music OSD, the action activates that dialog instead, and the OSD
        # covers our bar for as long as it is up.
        if xbmc.getCondVisibility("Window.IsActive(MusicOSD)"):
            xbmc.executebuiltin("Dialog.Close(MusicOSD)")

    def refresh_artwork(self, station):
        url = fetch_artwork(station)
        if not url:
            # Keep the last image that worked rather than blanking the screen.
            return
        window = xbmcgui.Window(VISUALISATION_WINDOW)
        if window.getProperty(ART_PROPERTY) != url:
            window.setProperty(ART_PROPERTY, url)
            xbmc.log("shirleyandspinoza: set %s = %s" % (ART_PROPERTY, url), xbmc.LOGINFO)

    def reconnect(self, station):
        if self.isPlaying():
            # An attempt is starting or playing: give it its head.
            return
        if time.time() > self.retry_until:
            self.give_up(station)
            return
        if time.time() < self.next_attempt:
            return
        self.next_attempt = time.time() + RECONNECT_SECONDS
        xbmc.log("shirleyandspinoza: reconnecting to %s" % station["name"], xbmc.LOGINFO)
        self.play(station["stream"])

    def give_up(self, station):
        with self.lock:
            self.state = IDLE
        xbmc.log("shirleyandspinoza: gave up on the stream", xbmc.LOGWARNING)
        clear_art()
        if xbmc.getCondVisibility("Window.IsActive(Visualisation)"):
            leave_view()
        xbmcgui.Dialog().notification(
            station["name"], "Stream lost", xbmcgui.NOTIFICATION_WARNING
        )


xbmc.log("shirleyandspinoza: service started", xbmc.LOGINFO)
drop_cached_listing()
service = StationService()  # must stay referenced or Kodi drops the callbacks
xbmc.Monitor().waitForAbort()
xbmc.log("shirleyandspinoza: service stopped", xbmc.LOGINFO)
