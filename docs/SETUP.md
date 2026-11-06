# Skully's orbit

This folder is ready to become the contents of the public
[`Skullfiredevil/Skullfiredevil`](https://github.com/Skullfiredevil/Skullfiredevil)
profile repository. The README and assets work as soon as they are uploaded.
No hosted stats service, API key, or personal access token is needed to display them.

## Put it on the profile

1. Copy `README.md`, `assets/`, `scripts/`, `tests/`, `requirements.txt`, and
   `.github/workflows/orbit.yml` into the existing profile repository. Include
   `docs/` to keep the README's setup link working.
2. Commit to `main` (the current profile repository's default branch).
3. Open **Actions → Refresh UFO → Run workflow**. Subsequent runs happen daily
   at **01:23 UTC**, subject to GitHub's scheduling delays.

The workflow requests `contents: write` to commit generated assets. If repository
or organization policy prevents that permission or protects `main`, the render
can succeed while the commit fails. Adjust that repository policy or run the
renderer locally and commit the generated assets yourself.

GitHub can pause scheduled workflows after 60 days of inactivity in a public
repository. Re-enable the workflow from Actions if that happens. The existing
animation stays visible even when updates stop.

## Render locally

Python 3.12+, [GitHub CLI](https://cli.github.com/), and a GitHub CLI login:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
gh auth login
python scripts/render_orbit.py --login Skullfiredevil
python -m unittest discover -s tests -v
```

To redraw the checked-in data without network access:

```sh
python scripts/render_orbit.py --snapshot assets/activity.json
```

Outputs are `assets/orbit.gif`, its still `assets/orbit.png`, and
`assets/activity.json`. Collection completes and validates before any file is
replaced, so a collection failure leaves the last good illustration in place.
Rendering is deterministic for the same snapshot and pinned Pillow version.

## What changes with activity?

| Visible detail | Data behind it |
| --- | --- |
| Lateral drift and hover height | Yesterday's contribution count |
| Beam brightness and floating pixels | Contributions in the last seven days |
| Saucer lights | Current streak ending yesterday; one running light is always on |
| Pixel field | Last 84 days, in 12 columns of 7 days; oldest at top left |
| Flight log | End date, rolling 365-day total, last 7 days, and current streak |
| Languages by repo count | Primary language per public owned repo; excludes forks and undetected languages, includes archived repos |
| Star positions | Stable seed from the GitHub username |

The renderer uses GitHub's contribution calendar, not a raw commit count. Counts
depend on GitHub's attribution rules and the authenticated viewer's visibility;
the workflow's built-in token has access to the profile repository, not your other
private repositories. The local CLI uses your own login and may see more. Only
daily aggregate counts, dates, and aggregate language counts are saved. Today's partial UTC day is excluded.
No fake contributions fill quiet days. The pilot still blinks when the log is quiet.

The first supplied asset was collected with the local CLI. Running the workflow
replaces it with the calendar visible to the workflow token.

Language percentages use all eligible public repositories as the denominator.
The six most common languages are shown; when there are more than six, the panel
shows the top five and groups the rest as **Other**. Each public repository counts
once, using GitHub's primary-language field rather than bytes of code. Repository
names are not stored. Pagination includes accounts with more than 100 repos.
The language panel and contribution calendar must both collect successfully before
the generated files are replaced.

## Design notes

- Mint `#a4f7cb`, space `#0b1117`, and a small lavender accent `#c2b7f5`.
- The ship is drawn at pixel resolution and enlarged with nearest-neighbor
  sampling. GIF animation works in GitHub README images without scripts or CSS.
- The illustration has its own dark background, including on GitHub's light theme.
- Text, links, and the toolkit remain normal Markdown/HTML for accessibility and
  narrow screens. The GIF alt text describes the scene; the activity snapshot
  provides a machine-readable version of the flight log.
- `orbit.png` is available if you prefer a still image: change the README image
  path from `.gif` to `.png`.

## Inspiration and credit

[git-koi](https://github.com/yalongwastaken/git-koi) by
[yalongwastaken](https://github.com/yalongwastaken) inspired the idea of a profile
creature shaped by GitHub activity. This UFO, animation, layout, and Python
renderer are original; no upstream code or artwork was copied.
