"""The station table.

One station so far. Another is a matter of appending an entry: the addon lists what is
here, and the service follows whichever entry is playing.

- name:       what Kodi shows for the station
- station_id: the radio.co station id, which also names it in plugin paths
- stream:     the audio stream Kodi plays
"""

API_BASE = "https://public.radio.co/stations"

STATIONS = [
    {
        "name": "Shirley & Spinoza Radio",
        "station_id": "sec5fa6199",
        "stream": "https://s2.radio.co/sec5fa6199/listen",
    },
]


def status_url(station):
    """The station's now-playing API, which carries the current track's artwork."""
    return "%s/%s/status" % (API_BASE, station["station_id"])
