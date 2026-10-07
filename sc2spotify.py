#!/usr/bin/env python3
"""Add SoundCloud tracks to a Spotify playlist.

Spotify playlists can only hold tracks from Spotify's own catalog, so this
reads each SoundCloud track's artist/title, searches Spotify for it, and adds
the best match to your playlist.

Usage:
    python sc2spotify.py "My Playlist" https://soundcloud.com/artist/track ...
    python sc2spotify.py <playlist-url-or-id> --file urls.txt --yes
"""
import argparse
import re
import sys
from difflib import SequenceMatcher

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from yt_dlp import YoutubeDL

SCOPE = "playlist-read-private playlist-modify-public playlist-modify-private"

# Bracketed promo junk common in SoundCloud titles: "(Free Download)", "[OUT NOW]", ...
NOISE = re.compile(
    r"[\(\[][^\)\]]*\b(free\s*(dl|download)|out\s*now|official|premiere|preview|"
    r"buy|exclusive|teaser|clip)\b[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
PREFIX = re.compile(r"^\s*(premiere|free\s*download|out\s*now)\s*[:|\-]\s*", re.IGNORECASE)
SEPARATORS = (" - ", " – ", " — ", " | ")


def clean(text):
    text = PREFIX.sub("", NOISE.sub("", text or ""))
    return re.sub(r"\s+", " ", text).strip(" -|")


def normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def parse_artist_title(info):
    """Best guess at (artist, title) for a SoundCloud track."""
    if info.get("artist") and info.get("track"):
        return clean(info["artist"]), clean(info["track"])
    title = clean(info.get("title"))
    for sep in SEPARATORS:
        if sep in title:
            artist, title = title.split(sep, 1)
            return artist.strip(), title.strip()
    # No "Artist - Title" pattern: assume the uploader is the artist.
    return clean(info.get("uploader")), title


def fetch_soundcloud(urls):
    """Yield metadata for every track behind the given URLs (tracks or sets)."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}
    with YoutubeDL(opts) as ydl:
        for url in urls:
            info = ydl.extract_info(url, download=False)
            if not info:
                print(f"  ! Could not read {url}", file=sys.stderr)
                continue
            entries = info.get("entries")
            if entries is None:
                yield info
            else:
                yield from (e for e in entries if e)


def find_on_spotify(sp, artist, title):
    """Return (best Spotify track, score 0-1) or (None, 0)."""
    queries = [f"track:{title} artist:{artist}", f"{artist} {title}"] if artist else [title]
    best, best_score = None, 0.0
    for query in queries:
        for track in sp.search(q=query, type="track", limit=5)["tracks"]["items"]:
            title_score = similarity(title, track["name"])
            if artist:
                artist_score = max(similarity(artist, a["name"]) for a in track["artists"])
                # Titles like "A x B" or "A & B" list several artists; credit partial hits.
                if any(normalize(a["name"]) in normalize(artist) for a in track["artists"]):
                    artist_score = max(artist_score, 0.9)
                score = 0.6 * title_score + 0.4 * artist_score
            else:
                score = title_score
            if score > best_score:
                best, best_score = track, score
        if best_score >= 0.85:
            break
    return best, best_score


def resolve_playlist(sp, ref):
    """Accept a playlist URL, URI, ID, or the name of one of your playlists."""
    match = re.search(r"playlist[/:]([A-Za-z0-9]{22})", ref)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", ref):
        return ref
    page = sp.current_user_playlists(limit=50)
    while page:
        for playlist in page["items"]:
            if playlist and playlist["name"].lower() == ref.lower():
                return playlist["id"]
        page = sp.next(page) if page.get("next") else None
    sys.exit(f"No playlist named {ref!r} found in your library.")


def existing_uris(sp, playlist_id):
    uris = set()
    page = sp.playlist_items(playlist_id)
    while page:
        for item in page["items"]:
            track = item.get("item") or item.get("track")
            if track and track.get("uri"):
                uris.add(track["uri"])
        page = sp.next(page) if page.get("next") else None
    return uris


def describe(track):
    return f"{', '.join(a['name'] for a in track['artists'])} - {track['name']}"


def ask(prompt, default):
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"    {prompt} {hint} ").strip().lower()
    return default if not answer else answer.startswith("y")


def main():
    parser = argparse.ArgumentParser(description="Add SoundCloud tracks to a Spotify playlist.")
    parser.add_argument("playlist", help="Spotify playlist URL, ID, or exact name")
    parser.add_argument("urls", nargs="*", help="SoundCloud track or set URLs")
    parser.add_argument("-f", "--file", help="text file with one SoundCloud URL per line")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="don't prompt; add matches scoring at least --min-score")
    parser.add_argument("--min-score", type=float, default=0.75,
                        help="match confidence threshold, 0-1 (default 0.75)")
    parser.add_argument("--dry-run", action="store_true", help="show matches without adding")
    args = parser.parse_args()

    urls = list(args.urls)
    if args.file:
        with open(args.file) as fh:
            urls += [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    if not urls:
        parser.error("give at least one SoundCloud URL or --file")

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope=SCOPE, open_browser=True))
    playlist_id = resolve_playlist(sp, args.playlist)
    already = existing_uris(sp, playlist_id)

    to_add, not_found, skipped = [], [], []
    for info in fetch_soundcloud(urls):
        artist, title = parse_artist_title(info)
        label = f"{artist} - {title}" if artist else title
        print(f"\n• SoundCloud: {label}")

        track, score = find_on_spotify(sp, artist, title)
        if not track:
            print("    No match on Spotify.")
            not_found.append(label)
            continue
        print(f"    Spotify:    {describe(track)}  (confidence {score:.0%})")

        if track["uri"] in already or track["uri"] in to_add:
            print("    Already in playlist, skipping.")
            continue
        accept = score >= args.min_score if args.yes else ask("Add this?", score >= args.min_score)
        if accept:
            to_add.append(track["uri"])
        else:
            skipped.append(label)

    if to_add and not args.dry_run:
        for i in range(0, len(to_add), 100):
            sp.playlist_add_items(playlist_id, to_add[i:i + 100])

    verb = "Would add" if args.dry_run else "Added"
    print(f"\n{verb} {len(to_add)} track(s).")
    if skipped:
        print(f"Skipped {len(skipped)}: " + "; ".join(skipped))
    if not_found:
        print(f"Not on Spotify ({len(not_found)}): " + "; ".join(not_found))


if __name__ == "__main__":
    main()
