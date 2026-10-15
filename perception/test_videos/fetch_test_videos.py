#!/usr/bin/env python3
"""Download the test clips in manifest.json from Wikimedia Commons and prepare them for PipeGen.

    python perception/test_videos/fetch_test_videos.py            # -> /home/$USER/wildguard_media
Produces, per clip, <id>.mp4 (H.264, 1280x720, 30 fps, no audio) plus:
  wildguard_demo_reel.mp4   all clips back to back (hard cuts, no black frames)
                            (use as PipeGen's file source and as the demo-day camera backup)
  ATTRIBUTION.md            author + licence for every clip (required by CC BY / BY-SA)
Needs ffmpeg (sudo apt install ffmpeg) or `pip install imageio-ffmpeg`.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "WildGuard-hackathon-test-fetch/1.0 (educational; Wikimedia Commons media)"}


def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: sudo apt install ffmpeg  (or pip install imageio-ffmpeg)")


def get(url, timeout=120, tries=6):
    """GET with backoff: Wikimedia answers 429 when downloads come too fast."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or i == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 10 * (i + 1)
            print(f"  server busy ({e.code}), retrying in {wait} s", flush=True)
            time.sleep(wait)


def info(title):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo",
                                "iiprop": "url|sha1|size|extmetadata", "format": "json"})
    page = next(iter(json.loads(get(f"{API}?{q}", timeout=30))["query"]["pages"].values()))
    ii = page["imageinfo"][0]
    m = ii["extmetadata"]
    artist = re.sub(r"<[^>]+>", "", m.get("Artist", {}).get("value", "unknown")).strip()
    return ii["url"].split("?")[0], ii["sha1"], m.get("LicenseShortName", {}).get("value", "?"), artist, ii["descriptionurl"]


def probe_seconds(ff, path) -> float:
    """Duration via ffmpeg's own report (works without ffprobe)."""
    r = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def main():
    out = Path(os.environ.get("WG_MEDIA_DIR", f"/home/{os.environ.get('USER', 'user')}/wildguard_media"))
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg()
    clips = json.loads((HERE / "manifest.json").read_text())["clips"]
    attrib = ["# Test video attribution", "", "| Clip | Source | Author | Licence |", "|---|---|---|---|"]
    prepared = []
    for c in clips:
        url, sha1, lic, artist, page = info(c["title"])
        src = raw / urllib.parse.unquote(url.rsplit("/", 1)[1])
        if not src.exists() or hashlib.sha1(src.read_bytes()).hexdigest() != sha1:
            print(f"download {c['id']} ...", flush=True)
            src.write_bytes(get(url))
            time.sleep(3)  # be polite to upload.wikimedia.org
            if hashlib.sha1(src.read_bytes()).hexdigest() != sha1:
                sys.exit(f"sha1 mismatch for {src.name}")
        dst = out / f"{c['id']}.mp4"
        if not dst.exists():
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-an",
                            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23", str(dst)], check=True)
        prepared.append(dst)
        attrib.append(f"| {c['id']} | [{c['title']}]({page}) | {artist} | {lic} |")
        print(f"ok  {c['id']:<20} {lic:<14} -> {dst}")

    # No black separators: PipeGen's run check samples frames and fails on a uniform (black) frame.
    lst = out / "_reel.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in prepared))
    reel = out / "wildguard_demo_reel.mp4"
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23", str(reel)], check=True)
    # where each clip sits in the reel (seconds) - lets tools/video_test.py score PipeGen's output per clip
    index, t = [], 0.0
    for c, p in zip(clips, prepared):
        dur = probe_seconds(ff, p)
        index.append({"id": c["id"], "expect": c["expect"], "start_s": round(t, 3), "end_s": round(t + dur, 3)})
        t += dur
    (out / "reel_index.json").write_text(json.dumps(index, indent=2))
    (out / "ATTRIBUTION.md").write_text("\n".join(attrib) + "\n")
    shutil.copy(out / "ATTRIBUTION.md", HERE / "ATTRIBUTION.md")
    print(f"\nreel -> {reel}\nindex -> {out / 'reel_index.json'}\nattribution -> {out / 'ATTRIBUTION.md'}")


if __name__ == "__main__":
    main()
