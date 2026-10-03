"""Where the addon's now-playing screen lives.

The service hangs the live artwork on the visualisation window's own property, the
binding Estuary's MusicVisualisation.xml reads:

    $INFO[Window(Visualisation).Property(ArtistSlideshow.Image)]

The plugin reads the same property back when the status API cannot supply an image, so
a failed poll keeps the last picture rather than blanking the screen.
"""

VISUALISATION_WINDOW = 12006
ART_PROPERTY = "ArtistSlideshow.Image"
