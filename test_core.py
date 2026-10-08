"""Run: python -m unittest -v test_core.py"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import wave

import core


def score(notes):
    return {'title': 'Test', 'artist': 'Artist', 'ppq': 960, 'end': 3840,
            'tempos': [{'tick': 0, 'bpm': 120}, {'tick': 1920, 'bpm': 60}],
            'signatures': [{'tick': 0, 'numerator': 4, 'denominator': 4}],
            'tracks': [{'index': 0, 'name': 'Drums', 'percussion': True, 'notes': notes}]}


def hit(tick, pitch, velocity=95):
    return {'tick': tick, 'pitch': pitch, 'velocity': velocity, 'length': 240}


class CoreTests(unittest.TestCase):
    def test_fast_kick_run_alternates_without_duplicating_hits(self):
        s = score([hit(t, 36) for t in range(0, 1440, 240)] + [hit(240, 42)])
        s['tempos'] = [{'tick': 0, 'bpm': 120}]
        chart, report = core.convert(s, 0, core.DEFAULT_MAP)
        for tick in [240, 720, 1200]:
            self.assertIn(f'{tick} = N 32 0', chart)
            self.assertNotIn(f'{tick} = N 0 0', chart)
        for tick in [0, 480, 960]:
            self.assertIn(f'{tick} = N 0 0', chart)
        self.assertIn('240 = N 66 0', chart)
        self.assertEqual(report['exported_hits'], 7)
        self.assertEqual(report['double_bass']['tagged_hits'], 3)

    def test_slower_than_sixteenth_kicks_stay_normal(self):
        s = score([hit(t, 36) for t in [0, 480, 960, 1440]])
        chart, report = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=200)
        self.assertNotIn('N 32', chart)
        self.assertEqual(report['double_bass']['tagged_hits'], 0)

    def test_double_bass_resets_after_a_pause(self):
        s = score([hit(t, 36) for t in [0, 240, 480, 1440, 1680, 1920, 2160]])
        chart, report = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=120)
        self.assertEqual([r['double_bass_ticks'] for r in report['double_bass']['runs']], [[240], [1680, 2160]])
        self.assertIn('1440 = N 0 0', chart)

    def test_entered_bpm_controls_eligibility_without_overwriting_tempos(self):
        s = score([hit(t, 36) for t in [0, 240, 480]])
        s['tempos'] = [{'tick': 0, 'bpm': 90}, {'tick': 120, 'bpm': 60}]
        chart, report = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=120)
        self.assertIn('240 = N 32 0', chart)
        self.assertIn('0 = B 90000', chart)
        self.assertIn('120 = B 60000', chart)
        self.assertEqual(report['double_bass']['song_bpm'], 120)

    def test_bpm_boundary_is_strictly_greater_than_110(self):
        s = score([hit(t, 36) for t in [0, 120, 240, 360]])
        for bpm in [60, 109, 110]:
            chart, _ = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=bpm)
            self.assertNotIn('N 32', chart)
        chart, _ = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=110.01)
        self.assertIn('120 = N 32 0', chart)
        self.assertIn('360 = N 32 0', chart)
        for bpm in [0, -1, float('nan'), float('inf')]:
            with self.assertRaises(core.AppError):
                core.convert(s, 0, core.DEFAULT_MAP, song_bpm=bpm)

    def test_consecutive_pair_and_faster_subdivisions_qualify(self):
        for gap in [240, 120, 60, 160]:
            s = score([hit(0, 36), hit(gap, 36)])
            chart, report = core.convert(s, 0, core.DEFAULT_MAP, song_bpm=120)
            self.assertIn(f'{gap} = N 32 0', chart)
            self.assertEqual(report['exported_hits'], 2)
        chart, _ = core.convert(score([hit(0, 36), hit(241, 36)]), 0, core.DEFAULT_MAP, song_bpm=120)
        self.assertNotIn('N 32', chart)

    def test_pro_drum_lanes_and_cymbal_flags(self):
        chart, report = core.convert(score([hit(0, 36), hit(0, 42), hit(480, 38), hit(960, 48),
                                           hit(1440, 51), hit(1920, 49)]), 0, core.DEFAULT_MAP)
        for line in ['0 = N 0 0', '0 = N 2 0', '0 = N 66 0', '480 = N 1 0', '960 = N 2 0',
                     '1440 = N 3 0', '1440 = N 67 0', '1920 = N 4 0', '1920 = N 68 0']:
            self.assertIn(line, chart)
        self.assertEqual(report['source_hits'], report['exported_hits'])
        self.assertNotIn('960 = N 66', chart)
        self.assertIn('[ExpertDrums]', chart)

    def test_colliding_tom_and_cymbal_block_strict_export(self):
        s = score([hit(0, 42), hit(0, 48)])
        with self.assertRaisesRegex(core.AppError, 'collisions'):
            core.convert(s, 0, core.DEFAULT_MAP)
        chart, report = core.convert(s, 0, core.DEFAULT_MAP, strict=False)
        self.assertEqual(report['exported_hits'], 1)
        self.assertEqual(report['collisions'][0]['pitches'], [42, 48])
        self.assertIn('0 = N 66 0', chart)

    def test_pedal_hat_is_not_silently_mapped(self):
        with self.assertRaisesRegex(core.AppError, 'Unmapped pitches: 44'):
            core.convert(score([hit(0, 44)]), 0, core.DEFAULT_MAP)
        mapping = dict(core.DEFAULT_MAP, **{})
        mapping[44] = 'Hi-hat / yellow cymbal'
        _, report = core.convert(score([hit(0, 44)]), 0, mapping)
        self.assertEqual(report['exported_hits'], 1)

    def test_explicit_ignore_is_audited(self):
        mapping = dict(core.DEFAULT_MAP)
        mapping[44] = 'Ignore'
        _, report = core.convert(score([hit(0, 36), hit(0, 44)]), 0, mapping)
        self.assertEqual(report['ignored'], {44: 1})
        self.assertEqual(report['source_hits'], 2)
        self.assertEqual(report['exported_hits'], 1)

    def test_dynamics_are_opt_in(self):
        s = score([hit(0, 38, 30), hit(960, 38, 120)])
        plain, _ = core.convert(s, 0, core.DEFAULT_MAP)
        dynamic, _ = core.convert(s, 0, core.DEFAULT_MAP, dynamics=True)
        self.assertNotIn('N 40', plain)
        self.assertIn('0 = N 40 0', dynamic)
        self.assertIn('960 = N 34 0', dynamic)

    def test_fractional_tick_is_not_claimed_lossless(self):
        with self.assertRaisesRegex(core.AppError, 'rounding'):
            core.convert(score([hit(0.4, 36)]), 0, core.DEFAULT_MAP)

    def test_written_dynamics_do_not_need_velocity_estimation(self):
        ghost, accent = hit(0, 38), hit(960, 38)
        ghost['ghost'] = True
        accent['accent'] = True
        chart, _ = core.convert(score([ghost, accent]), 0, core.DEFAULT_MAP)
        self.assertIn('0 = N 40 0', chart)
        self.assertIn('960 = N 34 0', chart)

    def test_meter_denominator_and_tempo_duration(self):
        s = score([hit(0, 36)])
        s['signatures'].append({'tick': 1920, 'numerator': 7, 'denominator': 8})
        chart, report = core.convert(s, 0, core.DEFAULT_MAP)
        self.assertIn('1920 = TS 7 3', chart)
        self.assertIn('1920 = B 60000', chart)
        self.assertAlmostEqual(report['duration_seconds'], 3)

    def test_export_is_complete_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            s = score([hit(0, 36)])
            folder, report = core.export_song(s, 0, core.DEFAULT_MAP, Path(d), offset_ms=200)
            second, _ = core.export_song(s, 0, core.DEFAULT_MAP, Path(d))
            self.assertNotEqual(folder, second)
            self.assertTrue((folder / 'notes.chart').is_file())
            chart = (folder / 'notes.chart').read_text()
            for name in ('Expert', 'Hard', 'Medium', 'Easy'):
                self.assertIn(f'[{name}Drums]', chart)
                self.assertGreater(report['downchart']['difficulties'][name]['hits'], 0)
            self.assertIn('pro_drums = True', (folder / 'song.ini').read_text())
            self.assertIn('delay = 200', (folder / 'song.ini').read_text())
            with wave.open(str(folder / 'song.wav')) as w:
                self.assertAlmostEqual(w.getnframes() / w.getframerate(), 6.2, places=3)
            self.assertEqual(json.loads((folder / 'conversion_report.json').read_text())['source_hits'], 1)

    def test_audio_copy_preserves_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            p = Path(d)
            audio = p / 'original.ogg'
            audio.write_bytes(b'OggS-test-audio')
            folder, _ = core.export_song(score([hit(0, 36)]), 0, core.DEFAULT_MAP, p, audio=audio)
            self.assertEqual((folder / 'song.ogg').read_bytes(), audio.read_bytes())

    def test_failed_strict_export_creates_no_folder(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as d:
            with self.assertRaises(core.AppError):
                core.export_song(score([hit(0, 44)]), 0, core.DEFAULT_MAP, Path(d))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_real_gp_import_repeat_tuplet_and_tempo(self):
        fixture = Path(__file__).with_name('demo.gp')
        s = core.read_gp(fixture)
        t = s['tracks'][0]
        self.assertTrue(t['percussion'])
        self.assertEqual(len(t['notes']), 80)
        self.assertEqual(s['end'], 15360)
        self.assertEqual([bar['tick'] for bar in s['bars']], [0, 3840, 7680, 11520])
        self.assertEqual([(x['tick'], x['bpm']) for x in s['tempos']],
                         [(0, 120), (3840, 90), (7680, 120), (11520, 90)])
        hat = [n['tick'] for n in t['notes'] if n['pitch'] == 42]
        self.assertEqual(hat[:8], list(range(0, 3840, 480)))
        self.assertEqual(hat[8:20], list(range(3840, 7680, 320)))
        self.assertEqual(sum(bool(n.get('ghost')) for n in t['notes']), 4)
        self.assertEqual(sum(bool(n.get('accent')) for n in t['notes']), 4)
        _, report = core.convert(s, 0, core.DEFAULT_MAP)
        self.assertEqual(report['exported_hits'], 80)
        self.assertAlmostEqual(report['duration_seconds'], 9 + 1/3)


if __name__ == '__main__':
    unittest.main()

