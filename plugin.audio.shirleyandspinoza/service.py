"""plugin.audio.shirleyandspinoza - the background service.

Estuary's MusicVisualisation.xml draws its fullscreen background from the visualisation
window's own property:

    <texture background="true">$INFO[Window(Visualisation).Property(ArtistSlideshow.Image)]</texture>

That property is the live-artwork hook: Player.updateInfoTag() was measured NOT to move
Player.Art(fanart) for the playing item, so it cannot swap the background, but setting
this window property can. This service opens the visualisation window when the station
starts and republishes radio.co's current artwork onto it as tracks change.
"""

import json
import urllib.request

import xbmc
import xbmcgui

STATUS_URL = "https://public.radio.co/stations/sec5fa6199/status"
STREAM_URL = "https://s2.radio.co/sec5fa6199/listen"
POLL_SECONDS = 15

VISUALISATION_WINDOW = 12006
ART_PROPERTY = "ArtistSlideshow.Image"

# radio.co's status API answers 403 to Python's default urllib user-agent.
USER_AGENT = "Kodi/21.3 (plugin.audio.shirleyandspinoza)"


class ArtworkPoller(xbmc.Player):
    def onAVStarted(self):
        if self.getPlayingFile() != STREAM_URL:
            return
        xbmc.executebuiltin("ActivateWindow(Visualisation)")
        self.poll()

    def poll(self):
        monitor = xbmc.Monitor()
        window = xbmcgui.Window(VISUALISATION_WINDOW)
        while not monitor.abortRequested():
            if not self.isPlaying():
                return
            url = self.artwork_url()
            if url:
                window.setProperty(ART_PROPERTY, url)
                xbmc.log("shirleyandspinoza: set %s = %s" % (ART_PROPERTY, url), xbmc.LOGINFO)
            if monitor.waitForAbort(POLL_SECONDS):
                return

    @staticmethod
    def artwork_url():
        request = urllib.request.Request(
            STATUS_URL,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
            return payload["current_track"].get("artwork_url_large")
        except Exception as error:
            xbmc.log("shirleyandspinoza: status fetch failed: %s" % error, xbmc.LOGWARNING)
            return None


xbmc.log("shirleyandspinoza: service started", xbmc.LOGINFO)
poller = ArtworkPoller()  # must stay referenced or Kodi drops the callbacks
xbmc.Monitor().waitForAbort()
xbmc.log("shirleyandspinoza: service stopped", xbmc.LOGINFO)
