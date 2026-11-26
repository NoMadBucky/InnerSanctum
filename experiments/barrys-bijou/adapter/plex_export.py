"""Build a token-free TMDb → Plex movie link map from a Plex Web XML page."""

from collections import defaultdict
import getpass
import json
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qs, urlsplit, urlencode
import urllib.request
from xml.etree import ElementTree as ET

from innersanctum import bijou, handover


def collect(container, server_id, matches):
    for movie in container.findall("Video"):
        key = movie.get("ratingKey", "")
        if movie.get("type") != "movie" or not re.fullmatch(r"[1-9]\d*", key):
            continue
        ids = {g.get("id", "") for g in movie.findall("Guid")} | {movie.get("guid", "")}
        for guid in ids:
            m = re.fullmatch(r"(?:tmdb://|com\.plexapp\.agents\.themoviedb://)([1-9]\d*)(?:\?.*)?", guid)
            if m:
                matches[m[1]].add((server_id, key))


def main():
    # The URL can carry an account token; don't echo it, persist it, or follow redirects with it.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args):
            return None

    pasted = getpass.getpass("Paste the View XML address from your own Plex server (input hidden): ").strip()
    u = urlsplit(pasted)
    if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password or not re.fullmatch(r"/library/metadata/\d+/?", u.path):
        sys.exit("Use the address of the View XML page for one movie on your own Plex server.")
    token = parse_qs(u.query).get("X-Plex-Token", [""])[0] or getpass.getpass("Local Plex access token (input hidden): ")
    if not token or not token.isascii() or not token.isalnum() and not re.fullmatch(r"[\w-]+", token):
        sys.exit("Invalid token.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def xml(path):
        req = urllib.request.Request(f"{u.scheme}://{u.netloc}{path}", headers={"X-Plex-Token": token, "Accept": "application/xml"})
        with opener.open(req, timeout=20) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024 or b"<!DOCTYPE" in raw.upper():
            raise ValueError("Unexpected Plex XML.")
        return ET.fromstring(raw)

    server = xml("/identity").get("machineIdentifier", "")
    if not re.fullmatch("[A-Za-z0-9-]{8,128}", server):
        sys.exit("Could not identify the Plex server.")
    dirs = [d for d in xml("/library/sections").findall("Directory") if d.get("type") == "movie" and d.get("key", "").isdigit()]
    if not dirs:
        sys.exit("No movie sections visible to this Plex account.")
    matches = defaultdict(set)
    for d in dirs:
        offset = 0
        while True:
            query = urlencode({"type": 1, "includeGuids": 1, "X-Plex-Container-Start": offset, "X-Plex-Container-Size": 100})
            page = xml(f"/library/sections/{d.get('key')}/all?{query}")
            if int(page.get("offset", 0)) != offset:
                sys.exit("Plex did not return the requested page.")
            collect(page, server, matches)
            count = len(page.findall("Video"))
            offset += count
            if offset >= int(page.get("totalSize", offset)):
                break
            if not count:
                sys.exit("Plex returned an incomplete library.")
    links = {k: list(next(iter(v))) for k, v in matches.items() if len(v) == 1}
    if not links:
        sys.exit("No unambiguous TMDb IDs were present. Existing links were left unchanged.")
    repo = Path(__file__).resolve().parents[3]
    with handover.live_checkout(repo) as (root, successor):
        cfg = bijou.personal_config(root, successor)
    state = Path.home() / "Library/Application Support" / ("BijouPersonal-" + cfg["library"])
    if state.resolve(strict=True) != state or not state.is_dir():
        sys.exit("The Personal adapter's private directory is unavailable.")
    with NamedTemporaryFile(mode="w", dir=state, delete=False) as f:
        json.dump(links, f)
    os.replace(f.name, state / "plex-movies.json")
    print(f"Saved {len(links)} exact TMDb matches. In Bijou, choose Home Sync → Sync now.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ET.ParseError, ValueError) as e:
        sys.exit(f"Export failed ({type(e).__name__}). Check the XML address and Plex access; no token is needed in chat.")
