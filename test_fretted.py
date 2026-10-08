import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from core import export_song, convert_song, DEFAULT_MAP, read_gp, AppError
from fretted import chart_fretted, prepare_events

def score_for(pitches, spacing=240, length=120, **flags):
    notes = []
    for index, group in enumerate(pitches):
        for pitch in (group if isinstance(group, list) else [group]):
            notes.append(dict(tick=index*spacing, pitch=pitch, length=length, velocity=90, **flags))
    return {'title': 'Original fixture', 'artist': 'Tests', 'ppq': 960,
            'tracks': [{'index': 0, 'name': 'Guitar', 'percussion': False, 'notes': notes}],
            'tempos': [{'tick': 0, 'bpm': 120}], 'signatures': [], 'sections': [], 'end': len(pitches)*spacing}

def expert_lanes(report):
    return [tuple(e['lanes']) for e in report['expert_pattern']]

class FrettedTests(unittest.TestCase):
    def test_five_pitch_run_and_reverse_preserve_direction(self):
        for pitches, expected in [([60,62,64,65,67], [(0,),(1,),(2,),(3,),(4,)]),
                                  ([67,65,64,62,60], [(4,),(3,),(2,),(1,),(0,)])]:
            _, report = chart_fretted(score_for(pitches), 0, 'Guitar')
            self.assertEqual(expert_lanes(report), expected)

    def test_long_scale_balances_windows_without_stranded_tail(self):
        _, report = chart_fretted(score_for([60,61,62,63,64,65]), 0, 'Guitar')
        self.assertEqual(expert_lanes(report), [(0,),(1,),(2,),(0,),(1,),(2,)])
        self.assertEqual(report['source_positions'], 6)

    def test_trills_and_repeated_pitch_remain_consistent(self):
        _, report = chart_fretted(score_for([60,67,60,67,60,60,67]), 0, 'Guitar')
        self.assertEqual(expert_lanes(report), [(0,),(1,),(0,),(1,),(0,),(0,),(1,)])

    def test_pitch_class_modulo_is_not_used_for_lanes(self):
        _, report = chart_fretted(score_for([60,65,70,75,80]), 0, 'Guitar')
        self.assertEqual(expert_lanes(report), [(0,),(1,),(2,),(3,),(4,)])

    def test_quarter_notes_do_not_all_collapse_to_green(self):
        _, report = chart_fretted(score_for([60,62,64,65,67], spacing=960, length=800), 0, 'Guitar')
        self.assertEqual(expert_lanes(report), [(0,),(1,),(2,),(3,),(4,)])

    def test_large_chords_are_reduced_and_repeated_shapes_are_stable(self):
        source = [[40,47,52,56,59,64], [42,49,54,58,61,66], [40,47,52,56,59,64]]
        _, report = chart_fretted(score_for(source), 0, 'Rhythm')
        lanes = expert_lanes(report)
        self.assertEqual(lanes[0], lanes[2])
        self.assertTrue(all(len(chord) <= 3 and max(chord)-min(chord) <= 3 for chord in lanes))

    def test_octave_doublings_use_one_fret(self):
        _, report = chart_fretted(score_for([[40,52,64]]), 0, 'Bass')
        self.assertEqual(expert_lanes(report), [(0,)])

    def test_sustains_have_release_gaps(self):
        chart, _ = chart_fretted(score_for([60,62], spacing=1920, length=1920), 0, 'Guitar')
        expert = chart.split('[HardSingle]')[0]
        self.assertIn('0 = N 0 1680', expert)

    def test_muted_notes_do_not_get_long_sustains(self):
        chart, _ = chart_fretted(score_for([60], length=1920, palm_mute=True), 0, 'Guitar')
        self.assertIn('0 = N 0 0', chart)

    def test_hopo_and_strum_flips_follow_notation(self):
        chart, _ = chart_fretted(score_for([60,62], hopo=False), 0, 'Guitar')
        self.assertIn('240 = N 5 0', chart.split('[HardSingle]')[0])
        chart, _ = chart_fretted(score_for([60,62], hopo=True), 0, 'Guitar')
        self.assertNotIn('240 = N 5 0', chart.split('[HardSingle]')[0])
        chart, _ = chart_fretted(score_for([60,60], hopo=True), 0, 'Guitar')
        self.assertIn('240 = N 5 0', chart.split('[HardSingle]')[0])

    def test_tap_and_optional_bass_open(self):
        chart, _ = chart_fretted(score_for([40], tap=True), 0, 'Bass')
        self.assertIn('0 = N 6 0', chart.split('[HardDoubleBass]')[0])
        chart, _ = chart_fretted(score_for([40], fret=0), 0, 'Bass', open_notes=True)
        self.assertIn('0 = N 7 0', chart.split('[HardDoubleBass]')[0])

    def test_lower_tiers_use_only_allowed_lanes_and_source_positions(self):
        chart, report = chart_fretted(score_for(list(range(60,88))), 0, 'Guitar')
        source_ticks = {e['tick'] for e in report['expert_pattern']}
        for difficulty, allowed in [('Expert',5),('Hard',5),('Medium',4),('Easy',3)]:
            section = chart.split(f'[{difficulty}Single]')[1].split('}')[0]
            positions = set()
            for tick, lane, length in re.findall(r'(\d+) = N (\d+) (\d+)', section):
                self.assertIn(int(tick), source_ticks)
                if int(lane) not in (5,6): self.assertLess(int(lane), allowed)
                positions.add(int(tick))
            self.assertTrue(positions)
        counts = [report['difficulties'][d]['positions'] for d in ['Expert','Hard','Medium','Easy']]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_all_three_instruments_export_without_drums(self):
        score = score_for([60,62,64,65,67])
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            selections = {role: {'track_index': 0, 'intensity_override': 3} for role in ['Guitar','Bass','Rhythm']}
            folder, report = export_song(score, None, {}, Path(tmp), fretted_tracks=selections)
            chart = (folder/'notes.chart').read_text()
            ini = (folder/'song.ini').read_text()
            for suffix in ['Single','DoubleBass','DoubleRhythm']:
                for difficulty in ['Expert','Hard','Medium','Easy']: self.assertIn(f'[{difficulty}{suffix}]',chart)
            self.assertNotIn('[ExpertDrums]',chart)
            self.assertNotIn('diff_drums',ini)
            self.assertIn('diff_guitar = 3',ini)
            self.assertIn('diff_bass = 3',ini)
            self.assertIn('diff_rhythm = 3',ini)
            self.assertEqual(len(report['instruments']),3)

    def test_drum_and_guitar_share_one_sync_and_events(self):
        score = read_gp(Path(__file__).parent/'demo.gp')
        pitched = score_for([60,62,64])['tracks'][0]; pitched['index'] = 1
        score['tracks'].append(pitched)
        chart, report = convert_song(score, 0, DEFAULT_MAP, fretted_tracks={'Guitar': {'track_index': 1}})
        self.assertEqual(chart.count('[SyncTrack]'),1)
        self.assertEqual(chart.count('[Events]'),1)
        self.assertIn('[ExpertDrums]',chart)
        self.assertIn('[ExpertSingle]',chart)

    def test_wrong_track_and_empty_selection_are_rejected(self):
        score = score_for([60])
        with self.assertRaises(ValueError): chart_fretted(score, 99, 'Guitar')
        with self.assertRaises(AppError): convert_song(score, None, {})

    def test_real_gp_repeat_and_written_techniques(self):
        score = read_gp(Path(__file__).parent/'demo-fretted.gp')
        self.assertEqual(len(score['tracks']), 3)
        self.assertEqual(score['tracks'][1]['program'], 33)
        self.assertTrue(any(n.get('hopo') for n in score['tracks'][0]['notes']))
        self.assertTrue(any(n.get('tap') for n in score['tracks'][0]['notes']))
        self.assertEqual(len(score['tracks'][0]['notes']), 32)
        chart, report = chart_fretted(score, 0, 'Guitar')
        pattern = expert_lanes(report)
        self.assertEqual(pattern[:16], pattern[16:])
        self.assertIn(' = N 6 0', chart.split('[HardSingle]')[0])
