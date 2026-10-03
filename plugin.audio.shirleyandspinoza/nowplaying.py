"""Where the addon's now-playing screen lives.

The service hangs the live artwork on the visualisation window's own property, the
binding Estuary's MusicVisualisation.xml reads:

    $INFO[Window(Visualisation).Property(ArtistSlideshow.Image)]

The plugin reads the same property back when the status API cannot supply an image, so
a failed poll keeps the last picture rather than blanking the screen.

The three calls that raise that screen live here rather than in the service because the
plugin needs them too: pressing the addon while a station is on air is the way back.
"""

import xbmc

VISUALISATION_WINDOW = 12006
ART_PROPERTY = "ArtistSlideshow.Image"


def show_view():
    """Raise the now-playing screen.

    The visualisation is Estuary's fullscreen music window; the music OSD is a dialog
    drawn over it. MusicVisualisation.xml shows the track bar -- cover, title, artist --
    only while Player.ShowInfo is set, which is the moment a track changes, or while the
    music OSD is open. Holding the OSD open is what keeps the bar on screen, and its
    buttons are what put play/pause and stop within reach of a remote.
    """
    # A modal dialog silently refuses a window activation, so clear the way first.
    xbmc.executebuiltin("Dialog.Close(all, true)")
    xbmc.executebuiltin("ActivateWindow(Visualisation)")
    xbmc.executebuiltin("ActivateWindow(MusicOSD)")


def leave_view():
    """Step back out of the now-playing screen. The music OSD is a dialog, so it has to
    go first or the window change is refused."""
    xbmc.executebuiltin("Dialog.Close(all, true)")
    xbmc.executebuiltin("ActivateWindow(Home)")
