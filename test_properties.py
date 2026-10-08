import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from core import read_gp, export_song, DEFAULT_MAP, AppError
from properties import estimate_intensity, chosen_intensity, validate_properties

class PropertiesTests(unittest.TestCase):
    score = {'ppq': 960, 'tempos': [{'tick': 0, 'bpm': 120}]}

    def test_fast_sustained_chart_rates_higher_than_sparse(self):
        sparse = [(t, 1) for t in range(0, 38400, 1920)]
        dense = [(t, 1) for t in range(0, 38400, 120)]
        self.assertGreater(estimate_intensity(self.score, dense)['estimated'], estimate_intensity(self.score, sparse)['estimated'])
        self.assertEqual(estimate_intensity(self.score, dense)['estimated'], 6)

    def test_marker_events_do_not_inflate_intensity(self):
        gems = [(t, 2) for t in range(0, 38400, 960)]
        extra = gems + [(t, 66) for t, _ in gems] + [(t, 41) for t, _ in gems]
        self.assertEqual(estimate_intensity(self.score, gems), estimate_intensity(self.score, extra))

    def test_tempo_changes_affect_speed(self):
        fast = dict(self.score, tempos=[{'tick': 0, 'bpm': 120}, {'tick': 960, 'bpm': 240}])
        gems = [(t, 1) for t in range(0, 38400, 240)]
        self.assertGreater(estimate_intensity(fast, gems)['metrics']['average_hits_per_second'], estimate_intensity(self.score, gems)['metrics']['average_hits_per_second'])

    def test_manual_zero_and_blank_auto(self):
        estimate = {'estimated': 4}
        self.assertEqual(chosen_intensity(estimate, '0')['selected'], 0)
        self.assertTrue(chosen_intensity(estimate, '0')['overridden'])
        self.assertEqual(chosen_intensity(estimate, '')['selected'], 4)
        for value in ('7', '-1', '2.5'):
            with self.assertRaises(ValueError): chosen_intensity(estimate, value)

    def test_metadata_validation(self):
        self.assertEqual(validate_properties({'album': ' Album ', 'album_track': '02'})['album_track'], '2')
        for metadata in ({'album': 'Title\nname = injected'}, {'preview_start_time': '-1'}, {'album_track': 'x'}, {'diff_guitar': '6'}):
            with self.assertRaises(ValueError): validate_properties(metadata)

    def test_export_properties_override_and_art(self):
        score = read_gp(Path(__file__).parent/'demo.gp')
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            art = Path(tmp)/'art.png'; art.write_bytes(b'test-image-copy')
            folder, report = export_song(score, 0, DEFAULT_MAP, Path(tmp)/'songs',
                properties={'album': 'Test album', 'genre': 'Rock', 'year': '2026', 'charter': 'My name',
                            'album_track': '2', 'preview_start_time': '12000', 'loading_phrase': 'Enjoy'},
                intensity_override=0, album_art=art)
            ini = (folder/'song.ini').read_text()
            self.assertIn('diff_drums = 0\n', ini)
            self.assertIn('diff_drums_real = 0\n', ini)
            self.assertIn('album = Test album\n', ini)
            self.assertIn('preview_start_time = 12000\n', ini)
            self.assertIn('Charter = "My name"', (folder/'notes.chart').read_text())
            self.assertEqual((folder/'album.png').read_bytes(), art.read_bytes())
            self.assertTrue(report['intensity']['overridden'])

    def test_invalid_override_creates_no_song(self):
        score = read_gp(Path(__file__).parent/'demo.gp')
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            parent = Path(tmp)/'songs'
            with self.assertRaises(AppError): export_song(score, 0, DEFAULT_MAP, parent, intensity_override=99)
            self.assertFalse(parent.exists())
