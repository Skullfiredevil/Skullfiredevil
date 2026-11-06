#!/usr/bin/env python3
"""Render an original pixel UFO from a GitHub contribution calendar.

No services at display time: GitHub serves the committed GIF directly.
Collection requires gh + authentication; rendering a saved snapshot is offline.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1200, 520)
BG = "#0b1117"
MINT = "#a4f7cb"
WHITE = "#edf4f0"
MUTED = "#8a9b99"
GRID = ["#1a2930", "#285347", "#3c8064", "#76bd91", MINT]
QUERY = """query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    login
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def collect(login: str, as_of: date) -> dict:
    """Read a rolling year, ending at the last complete UTC day."""
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}",
         "-f", f"login={login}",
         "-f", f"from={as_of - timedelta(days=364)}T00:00:00Z",
         "-f", f"to={as_of}T23:59:59Z"],
        check=True, capture_output=True, text=True, timeout=90,
    )
    data = json.loads(result.stdout)
    if data.get("errors"):
        raise ValueError(f"GitHub returned errors: {data['errors']}")
    user = data.get("data", {}).get("user")
    if not user or user["login"].lower() != login.lower():
        raise ValueError("GitHub did not return the requested account")
    days = [day for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]
            for day in week["contributionDays"]]
    snapshot = {"login": user["login"], "as_of": as_of.isoformat(), "days": days}
    snapshot["language_counts"] = collect_languages(login)
    validate(snapshot)
    return snapshot


def summarize_languages(pages: list) -> list[dict]:
    """One primary-language vote per public, owned, non-fork repository."""
    counts = Counter()
    for page in pages:
        if not isinstance(page, list):
            raise ValueError("GitHub did not return a repository list")
        for repo in page:
            name = repo.get("language")
            if not repo.get("fork") and not repo.get("private") and name:
                counts[name] += 1
    return [{"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))]


def collect_languages(login: str) -> list[dict]:
    # The public user endpoint excludes private repositories, even with a personal token.
    # --slurp preserves page boundaries; do not combine it with gh's --jq option.
    result = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", f"users/{login}/repos?per_page=100&type=owner"],
        check=True, capture_output=True, text=True, timeout=90,
    )
    return summarize_languages(json.loads(result.stdout))


def validate(snapshot: dict) -> None:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", snapshot["login"]):
        raise ValueError("Invalid GitHub login")
    end = date.fromisoformat(snapshot["as_of"])
    dates = []
    for day in snapshot["days"]:
        parsed = date.fromisoformat(day["date"])
        count = day["contributionCount"]
        if type(count) is not int or count < 0 or parsed > end:
            raise ValueError("Invalid contribution day")
        dates.append(parsed)
    expected = [end - timedelta(days=i) for i in range(364, -1, -1)]
    if dates != expected:
        raise ValueError("Snapshot must contain 365 consecutive days ending on as_of")
    languages = snapshot.get("language_counts", [])
    if not isinstance(languages, list):
        raise ValueError("Invalid language counts")
    seen = set()
    for language in languages:
        name, count = language["name"], language["count"]
        if not isinstance(name, str) or not name.strip() or name in seen or type(count) is not int or count < 1:
            raise ValueError("Invalid language count")
        seen.add(name)


def activity(snapshot: dict) -> dict:
    validate(snapshot)
    counts = [day["contributionCount"] for day in snapshot["days"]]
    streak = 0
    # A day off yesterday ends the streak. No grace day or invented activity.
    for count in reversed(counts):
        if not count:
            break
        streak += 1
    return {"year": sum(counts), "week": sum(counts[-7:]), "yesterday": counts[-1],
            "streak": streak, "recent": counts[-84:], "active": sum(c > 0 for c in counts)}


def font(size: int) -> ImageFont.FreeTypeFont:
    # Pillow bundles this font, so local and Actions renders use identical type.
    return ImageFont.load_default(size=size)


def label(draw: ImageDraw.ImageDraw, xy: tuple, text: str, fill=MUTED, size=14, spacing=2):
    x, y = xy
    for letter in text:
        draw.text((x, y), letter, font=font(size), fill=fill)
        x += draw.textlength(letter, font=font(size)) + spacing


def pixel_ufo(frame: int, stats: dict, seed: int) -> Image.Image:
    """A 180 x 120 pixel scene, scaled with nearest-neighbor sampling."""
    im = Image.new("RGB", (180, 120), BG)
    d = ImageDraw.Draw(im)
    phase = 2 * math.pi * frame / 72
    rng = random.Random(seed)
    # Stable star map. Brightness follows a smooth periodic function.
    for _ in range(32):
        x, y = rng.randrange(8, 173), rng.randrange(5, 111)
        bright = 72 + round(26 * math.sin(phase + rng.random() * 6.28))
        d.point((x, y), fill=(bright // 2, bright, bright - 5))
    d.line((14, 21, 18, 21), fill="#54776b")
    d.line((16, 19, 16, 23), fill="#54776b")
    d.line((154, 35, 160, 35), fill="#749f8b")
    d.line((157, 32, 157, 38), fill="#749f8b")
    # Activity adjusts hover amplitude and lateral travel; both loop exactly.
    cx = 91 + round((3 + min(stats["yesterday"], 16) / 2) * math.sin(phase))
    cy = 44 + round((2 + min(stats["yesterday"], 12) / 5) * math.cos(phase))
    power = min(stats["week"] / 35, 1)
    d.ellipse((cx-37, 106, cx+37, 111), fill="#10241f")
    # Stepped tractor beam: calm on quiet days, brighter with recent activity.
    for y in range(cy+16, 106, 3):
        t = (y-cy-16) / (106-cy-16)
        half = round(9 + t*23)
        strength = (1-t*.55) * (.75 + .15*math.sin(phase))
        color = (round(13+8*strength), round(30+(22+28*power)*strength),
                 round(27+(13+14*power)*strength))
        d.rectangle((cx-half, y, cx+half, min(y+2,105)), fill=color)
    for i in range(5 + round(power*5)):
        # A pixel fades near each end of its wrap to avoid a visible jump.
        t = (i/10 + frame/72) % 1
        x = cx + round(math.sin(i*4.1)*20*(1-t))
        y = round(102-t*(102-cy-16))
        strength = math.sin(math.pi*t)
        if strength > .3:
            d.rectangle((x,y,x+1,y+1), fill=(int(90*strength),int(186*strength),int(139*strength)))
    # Original saucer silhouette, layered in actual pixels.
    d.rectangle((cx-21,cy-10,cx+21,cy+1), fill="#34534e")
    d.rectangle((cx-17,cy-16,cx+17,cy-7), fill="#34534e")
    d.rectangle((cx-11,cy-20,cx+11,cy-11), fill="#34534e")
    d.rectangle((cx-9,cy-19,cx+9,cy-18), fill="#b4f5d6")
    d.rectangle((cx-15,cy-15,cx+15,cy-6), fill="#19362f")
    d.rectangle((cx-19,cy-9,cx+19,cy+1), fill="#19362f")
    # Tiny alien pilot, with a two-frame blink.
    d.rectangle((cx-6,cy-12,cx+6,cy-3), fill=MINT)
    d.rectangle((cx-8,cy-10,cx+8,cy-5), fill=MINT)
    d.rectangle((cx-4,cy-3,cx+4,cy), fill="#7ac69e")
    blink = frame in (41,42)
    if blink:
        d.line((cx-6,cy-7,cx-2,cy-7), fill=BG)
        d.line((cx+2,cy-7,cx+6,cy-7), fill=BG)
    else:
        d.polygon([(cx-6,cy-9),(cx-2,cy-7),(cx-2,cy-5),(cx-5,cy-6)], fill=BG)
        d.polygon([(cx+6,cy-9),(cx+2,cy-7),(cx+2,cy-5),(cx+5,cy-6)], fill=BG)
    d.line((cx-17,cy-10,cx-17,cy-6), fill="#619c85")
    d.point((cx-15,cy-13), fill=MINT)
    d.rectangle((cx-25,cy,cx+25,cy+2), fill="#84bfa7")
    d.rectangle((cx-34,cy+3,cx+34,cy+6), fill="#84bfa7")
    d.rectangle((cx-41,cy+7,cx+41,cy+10), fill="#84bfa7")
    d.rectangle((cx-45,cy+10,cx+45,cy+13), fill="#d4f4e3")
    d.rectangle((cx-41,cy+14,cx+41,cy+17), fill="#4c796a")
    d.rectangle((cx-32,cy+18,cx+32,cy+20), fill="#263f38")
    d.rectangle((cx-16,cy+21,cx+16,cy+22), fill="#80bd9d")
    # The first lamp is always a running light. Streaks light the others.
    lit = 1 + min(stats["streak"], 4)
    for i, x in enumerate(range(cx-28,cx+29,14)):
        color = MINT if i < lit else "#334e44"
        d.rectangle((x-2,cy+14,x+2,cy+15), fill=color)
    # A lavender antenna beacon provides a small second color.
    d.line((cx,cy-24,cx,cy-21), fill="#658078")
    d.rectangle((cx-1,cy-26,cx+1,cy-24), fill="#c2b7f5")
    return im


def backdrop(snapshot: dict, stats: dict) -> Image.Image:
    im = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,1199,519), radius=16, outline="#263a35", width=2)
    label(d, (46,30), "SKULLFIREDEVIL", fill=MINT, size=16, spacing=3)
    label(d, (855,32), "DESIGN / CODE / CURIOSITY", size=12, spacing=1)
    d.line((46,69,1153,69), fill="#22332e")
    label(d, (46,108), "TRANSMITTING FROM PORTUGAL", size=13, spacing=1.6)
    d.text((42,144), "A little", font=font(72), fill=WHITE)
    d.text((42,216), "out of orbit.", font=font(72), fill=MINT)
    d.text((46,318), "Interfaces. Full stacks. Strange experiments.", font=font(19), fill=MUTED)
    label(d, (46,373), "UNIDENTIFIED FLYING DEVELOPER", fill="#c2b7f5", size=12, spacing=1.5)
    d.line((46,420,1153,420), fill="#22332e")
    label(d, (46,443), "FLIGHT LOG", fill=MINT, size=12)
    d.text((46,466), snapshot["as_of"] + " / UTC", font=font(17), fill=WHITE)
    for x, value, title in [(302, stats["year"], "CONTRIBUTIONS / 365D"),
                             (610, stats["week"], "LAST 7 DAYS"),
                             (916, stats["streak"], "DAY STREAK")]:
        d.line((x-26,444,x-26,492), fill="#263a35")
        d.text((x,439), f"{value:,}", font=font(26), fill=WHITE)
        label(d, (x,479), title, size=10, spacing=1)
    return im


def draw_calendar(im: Image.Image, stats: dict) -> None:
    """Keep contribution pixels visible in front of the tractor beam."""
    d = ImageDraw.Draw(im)
    # Twelve columns with seven consecutive days each, ending on as_of.
    d.rectangle((794, 309, 974, 391), fill=BG)
    label(d, (803,383), "12 WEEKS IN ORBIT", size=10, spacing=1.3)
    for i, count in enumerate(stats["recent"]):
        level = 0 if count == 0 else min(4, 1 + int(math.log2(count)))
        x, y = 807+(i//7)*14, 315+(i%7)*9
        d.rounded_rectangle((x,y,x+9,y+7), radius=1, fill=GRID[level])


def language_rows(languages: list[dict]) -> list[dict]:
    ranked = sorted(languages, key=lambda item: (-item["count"], item["name"].casefold()))
    if len(ranked) <= 6:
        return ranked
    return ranked[:5] + [{"name": "Other", "count": sum(item["count"] for item in ranked[5:])}]


def draw_languages(im: Image.Image, snapshot: dict) -> None:
    """A quiet telemetry panel in the space between headline and ship."""
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((488,100,737,400), radius=10, fill="#101a20", outline="#263a35")
    label(d, (505,116), "LANGUAGES", fill=MINT, size=15, spacing=1.7)
    label(d, (505,139), "BY REPO COUNT", size=11, spacing=1.3)
    languages = snapshot.get("language_counts", [])
    total = sum(item["count"] for item in languages)
    if not total:
        d.text((505,203), "No language data yet.", font=font(16), fill=MUTED)
        d.text((505,229), "Waiting for a signal.", font=font(13), fill=MUTED)
        return
    for i, item in enumerate(language_rows(languages)):
        y = 172 + i*32
        name = item["name"]
        while d.textlength(name, font=font(15)) > 125:
            name = name[:-2].rstrip("…") + "…"
        d.text((505,y), name, font=font(15), fill=WHITE)
        value = f"{item['count']} / {item['count']/total:.0%}"
        d.text((720-d.textlength(value, font=font(12)), y+2), value, font=font(12), fill=MUTED)
        d.rounded_rectangle((505,y+22,720,y+25), radius=1, fill="#243932")
        width = max(1, round(215*item["count"]/total))
        d.rectangle((505,y+22,504+width,y+25), fill=MINT)
    d.line((505,371,720,371), fill="#263a35")
    label(d, (505,382), f"{total} PUBLIC REPOS / NO FORKS", size=9, spacing=.6)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        name = Path(temporary.name)
    name.replace(path)


def render(snapshot: dict, output: Path) -> None:
    import io

    stats = activity(snapshot)
    base = backdrop(snapshot, stats)
    seed = int.from_bytes(hashlib.sha256(snapshot["login"].lower().encode()).digest()[:4])
    # A fixed palette avoids color flicker and keeps unchanged renders identical.
    palette_source = base.copy()
    palette_source.paste(pixel_ufo(0, stats, seed).resize((540,360), Image.Resampling.NEAREST), (640,76))
    draw_calendar(palette_source, stats)
    draw_languages(palette_source, snapshot)
    palette = palette_source.quantize(colors=128)
    frames = []
    for i in range(72):
        scene = base.copy()
        # Clip the scene before it reaches the contribution grid and footer.
        ship = pixel_ufo(i, stats, seed).crop((0,0,180,92))
        scene.paste(ship.resize((540,276), Image.Resampling.NEAREST), (640,76))
        draw_calendar(scene, stats)
        draw_languages(scene, snapshot)
        frames.append(scene.quantize(palette=palette, dither=Image.Dither.NONE))
    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:],
                   duration=80, loop=0, optimize=True, disposal=1)
    atomic_write(output / "orbit.gif", buffer.getvalue())
    buffer = io.BytesIO()
    frames[0].convert("RGB").save(buffer, format="PNG", optimize=True)
    atomic_write(output / "orbit.png", buffer.getvalue())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", default="Skullfiredevil")
    parser.add_argument("--snapshot", type=Path, help="Render saved data without contacting GitHub")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date()-timedelta(days=1))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text()) if args.snapshot else collect(args.login, args.as_of)
    render(snapshot, args.output_dir)
    atomic_write(args.output_dir / "activity.json", (json.dumps(snapshot, indent=2)+"\n").encode())
    print(f"Rendered {snapshot['login']} through {snapshot['as_of']} → {args.output_dir}")


if __name__ == "__main__":
    main()
