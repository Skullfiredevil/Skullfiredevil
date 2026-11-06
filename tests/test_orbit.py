"""Boundary checks for the activity-derived parts of the illustration."""

from datetime import date, timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

spec = importlib.util.spec_from_file_location("orbit", Path(__file__).parents[1] / "scripts/render_orbit.py")
orbit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orbit)


def snapshot(tail=()):
    end = date(2026, 11, 5)
    counts = [0] * (365 - len(tail)) + list(tail)
    return {"login": "Skullfiredevil", "as_of": end.isoformat(), "days": [
        {"date": (end-timedelta(days=364-i)).isoformat(), "contributionCount": c}
        for i, c in enumerate(counts)]}


class ActivityTests(unittest.TestCase):
    def test_language_counts_cover_all_pages_and_filter_repositories(self):
        pages = [[{"language": "HTML", "fork": False},
                  {"language": "Ruby", "fork": True},
                  {"language": None, "fork": False}],
                 [{"language": "HTML", "fork": False, "archived": True},
                  {"language": "Ruby", "fork": False},
                  {"language": "Python", "private": True, "fork": False}]]
        self.assertEqual(orbit.summarize_languages(pages),
                         [{"name": "HTML", "count": 2}, {"name": "Ruby", "count": 1}])

    def test_language_collection_paginates(self):
        with patch.object(orbit.subprocess, "run") as run:
            run.return_value.stdout = '[[{"language":"Ruby","fork":false}],[{"language":"Ruby","fork":false}]]'
            self.assertEqual(orbit.collect_languages("Skullfiredevil"), [{"name": "Ruby", "count": 2}])
            self.assertIn("--paginate", run.call_args.args[0])
            self.assertIn("--slurp", run.call_args.args[0])

    def test_language_overflow_keeps_the_denominator(self):
        languages = [{"name": f"Language{i}", "count": i} for i in range(1, 9)]
        rows = orbit.language_rows(languages)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[-1], {"name": "Other", "count": 6})
        self.assertEqual(sum(row["count"] for row in rows), sum(row["count"] for row in languages))

    def test_invalid_language_counts_are_rejected(self):
        for count in (-1, 0, True, "5"):
            data = snapshot()
            data["language_counts"] = [{"name": "HTML", "count": count}]
            with self.subTest(count=count), self.assertRaises(ValueError):
                orbit.validate(data)

    def test_quiet_account_has_no_invented_activity(self):
        stats = orbit.activity(snapshot())
        self.assertEqual([stats[k] for k in ("year", "week", "streak", "yesterday", "active")], [0]*5)
        self.assertEqual(len(stats["recent"]), 84)

    def test_windows_and_streak_are_independent(self):
        stats = orbit.activity(snapshot([100, 2, 0, 3, 4, 0, 5, 6]))
        self.assertEqual(stats["year"], 120)
        self.assertEqual(stats["week"], 20)
        self.assertEqual(stats["yesterday"], 6)
        self.assertEqual(stats["streak"], 2)

    def test_yesterdays_zero_ends_streak(self):
        self.assertEqual(orbit.activity(snapshot([5, 6, 0]))["streak"], 0)

    def test_bad_calendar_is_rejected(self):
        for mutation in ("duplicate", "future", "negative", "missing"):
            with self.subTest(mutation=mutation):
                data = snapshot()
                if mutation == "duplicate":
                    data["days"][0] = data["days"][1].copy()
                elif mutation == "future":
                    data["days"][-1]["date"] = "2026-11-06"
                elif mutation == "negative":
                    data["days"][-1]["contributionCount"] = -1
                else:
                    data["days"].pop()
                with self.assertRaises(ValueError):
                    orbit.validate(data)

    def test_ship_motion_loops_and_activity_changes_it(self):
        stats = orbit.activity(snapshot())
        self.assertEqual(orbit.pixel_ufo(0, stats, 7).tobytes(), orbit.pixel_ufo(72, stats, 7).tobytes())
        active = orbit.activity(snapshot([20]*7))
        self.assertNotEqual(orbit.pixel_ufo(0, stats, 7).tobytes(), orbit.pixel_ufo(0, active, 7).tobytes())

    def test_valid_looping_gif_and_repeatable_output(self):
        data = snapshot([1, 2, 0, 5, 3, 2, 1])
        data["language_counts"] = [{"name": "JavaScript", "count": 10}, {"name": "Ruby", "count": 7}]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            orbit.render(data, output)
            first = (output / "orbit.gif").read_bytes()
            with Image.open(output / "orbit.gif") as gif:
                self.assertEqual(gif.size, (1200, 520))
                self.assertEqual(gif.n_frames, 72)
                self.assertEqual(gif.info["loop"], 0)
                for frame in range(gif.n_frames):
                    gif.seek(frame)
                    gif.load()
            orbit.render(data, output)
            self.assertEqual(first, (output / "orbit.gif").read_bytes())


if __name__ == "__main__":
    unittest.main()
