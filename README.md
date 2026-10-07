# soundcloud-to-spotify

[![CI](https://github.com/bhavyapuri15/soundcloud-to-spotify/actions/workflows/ci.yml/badge.svg)](https://github.com/bhavyapuri15/soundcloud-to-spotify/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A command-line tool that takes SoundCloud tracks or whole SoundCloud sets and adds them to a Spotify playlist.

```text
$ sc2spotify "Late Night" https://soundcloud.com/user/sets/finds

• SoundCloud: Fred again.. - Delilah (pull me out of this)
    Spotify:    Fred again.. - Delilah (pull me out of this)  (confidence 100%)
    Add this? [Y/n]
• SoundCloud: Bicep - Glue
    Spotify:    Bicep - Glue  (confidence 100%)
    Add this? [Y/n]
• SoundCloud: someone - unreleased bootleg edit
    No match on Spotify.

Added 2 track(s).
Not on Spotify (1): someone - unreleased bootleg edit
```

## How it works

Spotify playlists can only hold tracks from Spotify's own catalog, so the tool matches songs rather than copying audio:

1. **Read SoundCloud metadata.** Every track behind the given URLs (single tracks or sets) is resolved with [yt-dlp](https://github.com/yt-dlp/yt-dlp). Only metadata is fetched; nothing is downloaded.
2. **Clean up the title.** SoundCloud titles are messy, so promo tags like `[Free Download]`, `(OUT NOW)` and `PREMIERE:` are removed, and `Artist - Title` is split out even when a label or repost channel uploaded the track.
3. **Search Spotify.** It runs a fielded search (`track:… artist:…`) first and falls back to a free-text search.
4. **Score each candidate.** Results are ranked by fuzzy title (60%) and artist (40%) similarity, and collaborations such as `A x B` count as an artist match.
5. **Confirm and add.** You approve each match, or use `--yes` to add every match above a confidence threshold. Duplicates already in the playlist are skipped, and tracks are added in batches of 100.

## Installation

```sh
git clone https://github.com/bhavyapuri15/soundcloud-to-spotify.git
cd soundcloud-to-spotify
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

### Spotify credentials (one-time)

1. Create an app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
   - **Redirect URI:** `http://127.0.0.1:8888/callback`
   - **APIs used:** Web API
2. Export the app's credentials (add them to your shell profile to keep them):

   ```sh
   export SPOTIPY_CLIENT_ID=your-client-id
   export SPOTIPY_CLIENT_SECRET=your-client-secret
   export SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```

The first run opens a browser so you can log in to Spotify, and the token is then cached locally.

> If Spotify returns `403`, add your Spotify account under **User Management** in the app's dashboard, because apps in development mode only work for listed users.

## Usage

```sh
# Single tracks into a playlist, chosen by name (asks before each add)
sc2spotify "Chill Mix" https://soundcloud.com/artist/track-1 https://soundcloud.com/artist/track-2

# A whole SoundCloud set into a playlist, chosen by link, without prompts
sc2spotify https://open.spotify.com/playlist/XXXXXXXXXXXXXXXXXXXXXX https://soundcloud.com/user/sets/my-set --yes

# URLs from a file (see urls.example.txt), preview only
sc2spotify "Chill Mix" --file urls.txt --dry-run
```

| Option | Description |
| --- | --- |
| `playlist` | Spotify playlist link, URI, ID, or the exact name of one of your playlists |
| `urls` | SoundCloud track or set URLs |
| `-f, --file` | Text file with one SoundCloud URL per line (`#` lines are ignored) |
| `-y, --yes` | Don't prompt: add matches at or above `--min-score` and skip the rest |
| `--min-score` | Match confidence threshold from 0 to 1 (default `0.75`) |
| `--dry-run` | Show matches without changing the playlist |

## Limitations

- Tracks that exist only on SoundCloud, such as bootlegs, unreleased edits and DJ mixes, can't be added and are listed at the end.
- Matching relies on titles, so unusual titles can still produce a wrong match. Use the prompt or `--dry-run` to review matches.

## Development

```sh
pip install -e ".[dev]"
ruff check .
pytest
```

The tests are offline because they use a fake Spotify client, so they need no credentials.

## License

[MIT](LICENSE)
