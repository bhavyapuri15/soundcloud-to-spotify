import pytest

from sc2spotify import clean, find_on_spotify, parse_artist_title, resolve_playlist


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Song [Free Download]", "Song"),
        ("Song (OUT NOW on Label)", "Song"),
        ("PREMIERE: Artist - Song", "Artist - Song"),
        ("Song (Extended Mix)", "Song (Extended Mix)"),
        ("  Song   Name  ", "Song Name"),
        (None, ""),
    ],
)
def test_clean(raw, expected):
    assert clean(raw) == expected


@pytest.mark.parametrize(
    "info, expected",
    [
        ({"title": "Fred again.. - Delilah (pull me out of this)", "uploader": "label"},
         ("Fred again..", "Delilah (pull me out of this)")),
        ({"title": "Bicep – Glue [Free DL]", "uploader": "x"}, ("Bicep", "Glue")),
        ({"title": "Midnight City", "uploader": "M83"}, ("M83", "Midnight City")),
        ({"title": "ignored", "artist": "Forss", "track": "Flickermood"},
         ("Forss", "Flickermood")),
    ],
)
def test_parse_artist_title(info, expected):
    assert parse_artist_title(info) == expected


def track(name, *artists, uri="spotify:track:x"):
    return {"name": name, "artists": [{"name": a} for a in artists], "uri": uri}


class FakeSpotify:
    def __init__(self, results=(), playlists=()):
        self.results = list(results)
        self.playlists = list(playlists)

    def search(self, q, type, limit):
        return {"tracks": {"items": self.results}}

    def current_user_playlists(self, limit):
        return {"items": self.playlists, "next": None}


def test_find_prefers_best_match():
    sp = FakeSpotify([
        track("Glue - Remix", "Someone Else", uri="spotify:track:bad"),
        track("Glue", "Bicep", uri="spotify:track:good"),
    ])
    best, score = find_on_spotify(sp, "Bicep", "Glue")
    assert best["uri"] == "spotify:track:good"
    assert score > 0.95


def test_find_credits_collab_artists():
    sp = FakeSpotify([track("Latch", "Disclosure")])
    _, score = find_on_spotify(sp, "Disclosure x Sam Smith", "Latch")
    assert score >= 0.9


def test_find_no_results():
    assert find_on_spotify(FakeSpotify(), "Nobody", "Nothing") == (None, 0.0)


@pytest.mark.parametrize(
    "ref",
    [
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc",
        "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
        "37i9dQZF1DXcBWIGoYBM5M",
    ],
)
def test_resolve_playlist_by_link_or_id(ref):
    assert resolve_playlist(FakeSpotify(), ref) == "37i9dQZF1DXcBWIGoYBM5M"


def test_resolve_playlist_by_name():
    sp = FakeSpotify(playlists=[{"name": "Chill Mix", "id": "abc"}])
    assert resolve_playlist(sp, "chill mix") == "abc"


def test_resolve_playlist_missing_exits():
    with pytest.raises(SystemExit):
        resolve_playlist(FakeSpotify(), "Nope")
