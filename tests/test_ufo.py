from datetime import date, timedelta
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

spec = importlib.util.spec_from_file_location('ufo', Path(__file__).resolve().parents[1] / 'scripts/render_ufo.py')
ufo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ufo)


class FlightTests(unittest.TestCase):
    def test_completed_days_and_streak(self):
        today = date(2026, 11, 6)
        days = [{'date': str(today - timedelta(days=i)), 'contributionCount': n}
                for i, n in enumerate([999, 3, 2, 0, 4, 0, 1, 5, 100])]
        result = ufo.summarize(days, today)
        self.assertEqual((result['recent'], result['streak'], result['annual']), (15, 2, 115))
        self.assertEqual(result['as_of'], '2026-11-05')

    def test_idle_and_invalid_data(self):
        today = date(2026, 11, 6)
        yesterday = str(today - timedelta(days=1))
        self.assertEqual(ufo.summarize([{'date': yesterday, 'contributionCount': 0}], today)['streak'], 0)
        for days in ([], [{'date': yesterday, 'contributionCount': -1}]):
            with self.assertRaises(ValueError):
                ufo.summarize(days, today)

    def test_gif_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            state = {'annual': 800, 'recent': 48, 'streak': 12, 'live': True, 'as_of': '2026-11-05'}
            ufo.render(state, Path(folder))
            with Image.open(Path(folder) / 'ufo.gif') as image:
                self.assertEqual(image.size, (960, 400))
                self.assertEqual(image.n_frames, 64)
                self.assertEqual(image.info['loop'], 0)
                self.assertEqual(image.info['duration'], 80)
                image.seek(63)
                image.load()
            self.assertLess((Path(folder) / 'ufo.gif').stat().st_size, 3_000_000)

    def test_fetch_calendar(self):
        payload = {'data': {'user': {'contributionsCollection': {'contributionCalendar': {
            'weeks': [{'contributionDays': [{'date': '2026-11-05', 'contributionCount': 7}]}]
        }}}}}
        with patch.object(ufo.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            result = ufo.fetch_activity('Skullfiredevil', 'test-token', date(2026, 11, 6))
        self.assertEqual(result['recent'], 7)
        self.assertEqual(request.call_args.args[0].full_url, 'https://api.github.com/graphql')
        variables = json.loads(request.call_args.args[0].data)['variables']
        self.assertEqual(variables['to'], '2026-11-06T00:00:00Z')

    def test_api_error_is_not_silently_zero_activity(self):
        with patch.object(ufo.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"errors": [{"message": "denied"}]}')):
            with self.assertRaises(RuntimeError):
                ufo.fetch_activity('Skullfiredevil', 'test-token', date(2026, 11, 6))


if __name__ == '__main__':
    unittest.main()
