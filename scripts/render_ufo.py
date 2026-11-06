"""An original activity-driven UFO for a GitHub profile. No external art assets."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import urllib.request

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BG = '#080e1a'
MINT = '#b6ffd6'
QUERY = '''query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}'''


def fetch_activity(username, token, today):
    """Only completed UTC dates affect the animation; token never leaves GitHub."""
    start = today - timedelta(days=365)
    request = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': {
            'login': username, 'from': f'{start}T00:00:00Z',
            'to': f'{today}T00:00:00Z',
        }}).encode(),
        headers={'Authorization': f'Bearer {token}',
                 'Content-Type': 'application/json', 'User-Agent': 'git-ufo'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get('errors') or not payload.get('data', {}).get('user'):
        raise RuntimeError('GitHub did not return a contribution calendar; keeping existing artwork.')
    weeks = payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
    return summarize([day for week in weeks for day in week['contributionDays']], today)


def summarize(days, today):
    counts = {}
    for day in days:
        day_date = date.fromisoformat(day['date'])
        count = day['contributionCount']
        if type(count) is not int or count < 0:
            raise ValueError('Contribution counts must be nonnegative integers')
        if today - timedelta(days=365) <= day_date < today:
            counts[day_date] = count
    if not counts:
        raise ValueError('Contribution calendar contains no completed days')
    recent = sum(counts.get(today - timedelta(days=i), 0) for i in range(1, 8))
    streak = 0
    cursor = today - timedelta(days=1)
    while counts.get(cursor, 0) > 0:
        streak += 1
        cursor -= timedelta(days=1)
    return {'annual': sum(counts.values()), 'recent': recent, 'streak': streak,
            'as_of': str(today - timedelta(days=1)), 'live': True}


def font(size):
    # Pillow's bundled font avoids a dependency on system-installed fonts.
    return ImageFont.load_default(size=size)


def draw_frame(index, state):
    """Draw a crisp pixel scene, then add legible full-resolution typography."""
    phase = 2 * math.pi * index / 64
    energy = min(state['recent'] / 35, 1)
    orbit = min(state['streak'], 14) / 14
    im = Image.new('RGB', (480, 200), BG)
    d = ImageDraw.Draw(im)
    rng = random.Random(42)

    # Fixed star positions avoid flicker between nightly builds.
    for i in range(42 + min(state['annual'] // 20, 40)):
        x, y = rng.randrange(18, 465), rng.randrange(22, 165)
        intensity = int(95 + 35 * math.sin(phase + i * 1.7))
        d.point((x, y), fill=(intensity // 2, intensity, intensity))
        if i % 11 == 0:
            d.line((x-1, y, x+1, y), fill='#91bcba')
            d.line((x, y-1, x, y+1), fill='#91bcba')

    # Tiny distant ringed planet and large quiet lunar horizon.
    d.ellipse((374, 42, 392, 60), fill='#27354d')
    d.arc((367, 45, 400, 58), 0, 185, fill='#6e7d9b', width=1)
    d.ellipse((-90, 160, 570, 400), fill='#101d2c', outline='#23384a', width=1)
    d.arc((10, 177, 470, 315), 185, 345, fill='#1a2d3c')
    d.ellipse((95, 178, 117, 182), fill='#0c1724', outline='#1b2c3d')
    d.ellipse((365, 186, 400, 191), fill='#0c1724', outline='#1b2c3d')

    x = round(240 + (9 + orbit * 12) * math.sin(phase))
    y = round(91 + 4 * math.cos(phase))

    # The tractor beam is blended below the ship; a gentle endless pulse.
    beam = Image.new('RGBA', im.size)
    b = ImageDraw.Draw(beam)
    strength = int(12 + energy * 13 + 4 * math.sin(phase))
    b.polygon([(x-17, y+14), (x+17, y+14), (x+56, 177), (x-56, 177)],
              fill=(108, 255, 188, strength))
    b.polygon([(x-9, y+14), (x+9, y+14), (x+30, 177), (x-30, 177)],
              fill=(108, 255, 188, strength + 8))
    im = Image.alpha_composite(im.convert('RGBA'), beam).convert('RGB')
    d = ImageDraw.Draw(im)
    d.ellipse((x-51, 171, x+51, 181), outline='#315b53')
    d.ellipse((x-31, 173, x+31, 179), outline='#507f6a')
    for i in range(9):
        travel = (index / 64 + i / 9) % 1
        px = x + int(math.sin(i * 19) * 27 * (1-travel))
        py = int(173 - travel * (173-y-15))
        d.rectangle((px, py, px+1, py+1), fill='#689c7b')

    # Pixel-stepped glass dome, tiny green pilot, metallic saucer.
    d.polygon([(x-27,y-5),(x-27,y-18),(x-23,y-18),(x-23,y-26),
               (x-16,y-26),(x-16,y-31),(x+16,y-31),(x+16,y-26),
               (x+23,y-26),(x+23,y-18),(x+27,y-18),(x+27,y-5)],
              fill='#234746', outline='#76bea6')
    d.line((x-19,y-20,x-19,y-13), fill='#c9ffe0', width=2)
    d.line((x-16,y-25,x-10,y-25), fill='#c9ffe0', width=2)
    d.rectangle((x-8,y-16,x+8,y-5), fill='#709f8b')
    d.polygon([(x-9,y-19),(x-6,y-23),(x+6,y-23),(x+9,y-19),
               (x+7,y-11),(x+2,y-7),(x-2,y-7),(x-7,y-11)], fill=MINT)
    blink = index in (45, 46)
    if blink:
        d.line((x-6,y-15,x-3,y-15), fill=BG)
        d.line((x+3,y-15,x+6,y-15), fill=BG)
    else:
        d.polygon([(x-7,y-18),(x-2,y-16),(x-2,y-12),(x-5,y-13)], fill=BG)
        d.polygon([(x+7,y-18),(x+2,y-16),(x+2,y-12),(x+5,y-13)], fill=BG)
    d.polygon([(x-28,y-7),(x+28,y-7),(x+36,y-3),(x+46,y+1),
               (x+52,y+6),(x+44,y+12),(x+28,y+18),(x-28,y+18),
               (x-44,y+12),(x-52,y+6),(x-46,y+1),(x-36,y-3)],
              fill='#526c7a', outline='#a1b9bc')
    d.polygon([(x-49,y+7),(x+49,y+7),(x+42,y+12),(x+26,y+17),
               (x-26,y+17),(x-42,y+12)], fill='#253c4d')
    d.line((x-44,y+5,x+44,y+5), fill='#d2e3d9', width=2)
    for i, offset in enumerate((-31,-16,0,16,31)):
        color = MINT if (index // 8 + i) % 5 < 2 else '#648b81'
        d.rectangle((x+offset-2,y+9,x+offset+2,y+11), fill=color)
    d.rectangle((x-12,y+18,x+12,y+20), fill='#8cd5a7')

    im = im.resize((960,400), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(im)
    d.text((32,25), 'S / F     /     DEEP SPACE OBSERVATORY', font=font(13), fill='#9badbd')
    d.ellipse((803,30,809,36), fill=MINT)
    d.text((820,25), 'VISITOR 001', font=font(12), fill=MINT)
    d.text((32,353), 'SOMEWHERE BEYOND THE ORDINARY.', font=font(12), fill='#a9bdc7')
    label = 'AWAITING FIRST TRANSMISSION'
    if state['live']:
        label = f"{state['recent']} SIGNALS / 7D   ·   {state['streak']}D ORBIT"
    width = d.textlength(label, font=font(12))
    d.text((928-width,353), label, font=font(12), fill='#9ad2b4')
    return im


def render(state, output):
    frames = [draw_frame(i, state) for i in range(64)]
    # One palette for the whole loop prevents color shimmer.
    palette = frames[0].quantize(colors=128)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / 'ufo.tmp.gif'
    frames[0].save(temporary, save_all=True, append_images=frames[1:],
                   duration=80, loop=0, optimize=False, disposal=2)
    temporary.replace(output / 'ufo.gif')
    draw_frame(0, state).save(output / 'ufo-still.png')
    (output / 'flight.json').write_text(json.dumps(state, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='Skullfiredevil')
    parser.add_argument('--offline', action='store_true', help='Render an honest waiting state without network access')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', args.username):
        parser.error('Invalid GitHub username')
    state = {'annual': 0, 'recent': 0, 'streak': 0, 'as_of': None, 'live': False}
    if not args.offline:
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if not token:
            parser.error('Set GH_TOKEN or GITHUB_TOKEN, or use --offline for the waiting state')
        state = fetch_activity(args.username, token, datetime.now(timezone.utc).date())
    render(state, args.output)
    print(f'Rendered {args.output / "ufo.gif"}')


if __name__ == '__main__':
    main()
