"""Where the addon's now-playing screen lives.

The screen is two windows: Estuary's visualisation (12006) as the moving background, and the
addon's own bar (`resources/skins/Default/1080i/nowplaying.xml`) as a dialog over it.

The bar is ours because the skin's cannot be repaired. Its cover is the playing item's own
art, fixed when the stream was resolved -- ticket 13 measured that nothing moves it: not
`Player.updateInfoTag()`, not any of Kodi 21's 174 JSON-RPC methods -- and its right-hand
cluster of buttons carries controls a live stream has no use for. Ours reads the artwork
from the window property below instead, which the service keeps current, so the cover
follows the tracks; its title and artist are the stream's ICY metadata; its elapsed
readout is `Player.Time`; and its transport is two buttons. Its top line -- the station's
name, and a wall clock -- stands in for the skin's top bar, which Kodi draws only while a
seek bar or the music OSD is up, neither of which this screen uses.

The service hangs the live artwork on the visualisation window's own property, the binding
Estuary's MusicVisualisation.xml reads for the background:

    $INFO[Window(Visualisation).Property(ArtistSlideshow.Image)]

The plugin reads the same property back when the status API cannot supply an image, so a
failed poll keeps the last picture rather than blanking the screen.

The bar's top line reads a property of ours in the same way:

    $INFO[Window(Visualisation).Property(Station.Name)]

The calls that raise and dismiss the screen live here rather than in the service because the
plugin needs them too: pressing the addon while a station is on air is the way back.
"""

import os
import threading

import xbmc
import xbmcaddon
import xbmcgui

VISUALISATION_WINDOW = 12006
ART_PROPERTY = "ArtistSlideshow.Image"
STATION_PROPERTY = "Station.Name"
SCRIM_PROPERTY = "Scrim.Texture"

BAR_XML = "nowplaying.xml"
BAR_SKIN = "Default"
BAR_RES = "1080i"

# The addon's own band texture. Skin XML cannot name an addon's own files, so the path
# travels to the window as a property (set in show_view, before the bar is built).
SCRIM_TEXTURE = os.path.join(
    xbmcaddon.Addon().getAddonInfo("path"), "resources", "nowplaying-scrim.png"
)

# Control ids in nowplaying.xml.
DISMISS = 899
PLAY_PAUSE = 900
STOP = 901

_bar = None
_bar_lock = threading.Lock()


class NowPlayingBar(xbmcgui.WindowXMLDialog):
    """The bar itself. Nothing has to be pushed into it: the cover reads the artwork window
    property, the title and artist read the player, and the clock reads the player's time.
    Only the buttons need code."""

    def onClick(self, control):
        # A dialog hands its bare XML buttons over as the control id, not the Control
        # object the docs describe; take either.
        control_id = control if isinstance(control, int) else control.getId()
        if control_id == PLAY_PAUSE:
            xbmc.executebuiltin("PlayerControl(Play)")
        elif control_id == STOP:
            xbmc.executebuiltin("PlayerControl(Stop)")
            self.close()
        elif control_id == DISMISS:
            self.close()

    def onAction(self, action):
        # Back is the way out on a remote or a controller. Playback carries on behind.
        if action.getId() in (
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_PARENT_DIR,
        ):
            self.close()


def _run_bar(window):
    """doModal() blocks until the bar closes, so it gets a thread of its own. show() will
    not do: for a dialog it puts the window up for one frame and Kodi then takes it back
    down, which is what the log shows as an Init and a Deinit 17ms apart."""
    global _bar
    try:
        window.doModal()
    finally:
        with _bar_lock:
            if _bar is window:
                _bar = None


def open_bar():
    """Put the bar over the visualisation. False if it cannot be built at all, which is the
    service's cue to fall back to the skin's own bar."""
    global _bar
    with _bar_lock:
        if _bar is not None:
            return True
        try:
            addon_path = xbmcaddon.Addon().getAddonInfo("path")
            window = NowPlayingBar(BAR_XML, addon_path, BAR_SKIN, BAR_RES)
        except Exception as error:
            xbmc.log(
                "shirleyandspinoza: cannot build the now-playing window: %s" % error,
                xbmc.LOGERROR,
            )
            return False
        _bar = window
    threading.Thread(target=_run_bar, args=(window,), daemon=True).start()
    return True


def close_bar():
    global _bar
    with _bar_lock:
        window, _bar = _bar, None
    if window is not None:
        window.close()


def bar_open():
    return _bar is not None


def clear_art():
    """Take our artwork back out of the shared property. Left there, the visualisation of
    whatever plays next -- a local file, another addon -- shows the station's cover."""
    xbmcgui.Window(VISUALISATION_WINDOW).clearProperty(ART_PROPERTY)


def show_view(station):
    """Raise the now-playing screen: the fullscreen visualisation, then our bar over it. If
    the bar cannot be built, the skin's own music OSD still gives the track info and the
    transport -- with the frozen cover and the buttons that come with it. The station goes
    onto the window first, because the bar's top line is a binding to its name."""
    # Before the bar opens: these are the bindings its window reads.
    view = xbmcgui.Window(VISUALISATION_WINDOW)
    view.setProperty(STATION_PROPERTY, station["name"])
    view.setProperty(SCRIM_PROPERTY, SCRIM_TEXTURE)
    # executebuiltin queues: without wait the visualisation would be activated after our
    # dialog went up, and activating a window takes the dialog back down.
    # Close the skin's bar by name rather than with Dialog.Close(all): a close-all lands on
    # the next frame, which is one frame after this dialog goes up, so it takes ours too.
    if bar_open() and xbmc.getCondVisibility("Window.IsActive(Visualisation)"):
        # Already ours. Activating the visualisation again would take the bar down with
        # it -- a window activation closes the dialog over it -- and rebuilding it is what
        # used to raise the skin's OSD instead. This is the path a paused live stream
        # reopens on, so the guard has to sit before the activation.
        return
    xbmc.executebuiltin("Dialog.Close(MusicOSD)", wait=True)
    xbmc.executebuiltin("ActivateWindow(Visualisation)", wait=True)
    if not open_bar():
        xbmc.executebuiltin("ActivateWindow(MusicOSD)", wait=True)


def leave_view():
    """Step back out of the now-playing screen."""
    close_bar()
    xbmc.executebuiltin("Dialog.Close(MusicOSD)", wait=True)
    xbmc.executebuiltin("ActivateWindow(Home)", wait=True)
