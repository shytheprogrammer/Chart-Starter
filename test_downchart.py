import copy
import unittest

from downchart import downchart


PPQ = 960


def fixture(bpm=120, bars=4):
    return {'ppq': PPQ, 'end': bars * 4 * PPQ,
            'tempos': [{'tick': 0, 'bpm': bpm}],
            'signatures': [{'tick': 0, 'numerator': 4, 'denominator': 4}], 'sections': []}


def groove(bars=4):
    gems = []
    for bar in range(bars):
        start = bar * 4 * PPQ
        for tick in range(start, start + 4 * PPQ, PPQ // 2):
            gems += [(tick, 2), (tick, 66)]
        gems += [(start, 0), (start + PPQ, 1), (start + 2 * PPQ, 0), (start + 3 * PPQ, 1)]
    return sorted(gems)


def notes(gems):
    return {(tick, lane) for tick, lane in gems if lane <= 4}


def times(gems, lane):
    return [tick for tick, value in gems if value == lane]


class DownchartTests(unittest.TestCase):
    def test_cascade_is_a_subset_with_no_shifted_or_invented_notes(self):
        expert = groove()
        expert += [(240, 1), (240, 40), (720, 0), (1200, 32), (1440, 3)]
        original = copy.deepcopy(expert)
        tiers, report = downchart(fixture(), expert, 120)
        parent = notes(expert)
        for name in ('Hard', 'Medium', 'Easy'):
            current = notes(tiers[name])
            self.assertTrue(current <= parent)
            self.assertGreater(len(current), 0)
            parent = current
        self.assertEqual(expert, original)
        self.assertEqual(report['difficulties']['Expert']['double_bass_hits'], 1)
        for gems in tiers.values():
            self.assertNotIn(32, [lane for _, lane in gems])

    def test_medium_keeps_eighth_timekeeping_below_140(self):
        tiers, _ = downchart(fixture(139, 1), groove(1), 139)
        self.assertEqual(times(tiers['Medium'], 2), list(range(0, 4 * PPQ, PPQ // 2)))
        self.assertEqual(times(tiers['Medium'], 1), [PPQ, 3 * PPQ])
        self.assertEqual(times(tiers['Medium'], 0), [0, 2 * PPQ])

    def test_medium_at_140_reduces_timekeeping_to_quarters(self):
        tiers, _ = downchart(fixture(140, 1), groove(1), 140)
        self.assertEqual(times(tiers['Hard'], 2), list(range(0, 4 * PPQ, PPQ // 2)))
        self.assertEqual(times(tiers['Medium'], 2), list(range(0, 4 * PPQ, PPQ)))

    def test_fast_kick_limit_and_backbeat_survive(self):
        tiers, report = downchart(fixture(170), groove(), 170)
        self.assertEqual(len(times(tiers['Medium'], 0)), 4)
        self.assertEqual(len(times(tiers['Easy'], 0)), 4)
        self.assertEqual(len(times(tiers['Easy'], 1)), 8)
        self.assertLessEqual(report['difficulties']['Medium']['max_simultaneous_limbs'], 2)

    def test_medium_does_not_chart_three_limb_chords(self):
        expert = groove(1) + [(PPQ, 0), (0, 4), (0, 68)]
        tiers, report = downchart(fixture(120, 1), expert, 120)
        counts = {}
        for tick, _ in notes(tiers['Medium']):
            counts[tick] = counts.get(tick, 0) + 1
        self.assertLessEqual(max(counts.values()), 2)
        self.assertIn((0, 4), notes(tiers['Medium']))
        self.assertIn((0, 0), notes(tiers['Medium']))
        self.assertEqual(report['difficulties']['Medium']['max_simultaneous_limbs'], 2)

    def test_hard_retains_short_slow_rolls_but_removes_kick_underneath(self):
        expert = [(tick, 1) for tick in range(0, 2 * PPQ + 1, PPQ // 4)] + [(0, 0), (PPQ, 0)]
        tiers, _ = downchart(fixture(120, 1), expert, 120)
        self.assertEqual(times(tiers['Hard'], 1), list(range(0, 2 * PPQ + 1, PPQ // 4)))
        self.assertEqual(times(tiers['Hard'], 0), [])
        self.assertEqual(times(tiers['Medium'], 1), list(range(0, 2 * PPQ + 1, PPQ // 2)))

    def test_hard_fast_or_sustained_rolls_are_thinned(self):
        for bpm, length in [(140, 2 * PPQ), (120, 4 * PPQ)]:
            expert = [(tick, 1) for tick in range(0, length, PPQ // 4)]
            tiers, _ = downchart(fixture(bpm, 1), expert, bpm)
            self.assertGreaterEqual(min(b - a for a, b in zip(times(tiers['Hard'], 1), times(tiers['Hard'], 1)[1:])), PPQ / 2)

    def test_medium_thins_fills_without_erasing_them(self):
        expert = [(0, 2), (0, 66), (480, 2), (480, 66), (960, 1), (960, 2), (960, 66)]
        expert += [(t, 3) for t in [1920, 2160, 2400, 2640, 2880, 3120]]
        tiers, _ = downchart(fixture(120, 1), expert, 120)
        self.assertEqual(times(tiers['Medium'], 3), [1920, 2400, 2880])

    def test_medium_removes_isolated_snare_between_timekeeper_notes(self):
        expert = groove(1) + [(720, 1)]
        tiers, _ = downchart(fixture(170, 1), expert, 170)
        self.assertNotIn((720, 1), notes(tiers['Medium']))
        self.assertIn((PPQ, 1), notes(tiers['Medium']))

    def test_offbeat_cymbals_do_not_erase_the_entire_medium_groove(self):
        expert = [(0, 0), (960, 1), (1920, 0), (2880, 1)]
        for tick in [480, 1440, 2400, 3360]:
            expert += [(tick, 2), (tick, 66)]
        tiers, _ = downchart(fixture(150, 1), expert, 150)
        self.assertEqual(notes(tiers['Medium']), {(0, 0), (960, 1), (1920, 0), (2880, 1)})

    def test_easy_never_pairs_cymbal_and_kick_and_uses_stable_sections(self):
        score = fixture(120, 24)
        score['sections'] = [{'tick': 0, 'name': 'Verse'}, {'tick': 8 * 4 * PPQ, 'name': 'Chorus'},
                             {'tick': 16 * 4 * PPQ, 'name': 'Bridge'}]
        expert = groove(24) + [(0, 4), (0, 68)]
        tiers, report = downchart(score, expert, 120)
        easy = notes(tiers['Easy'])
        for tick, lane in tiers['Easy']:
            if lane in (66, 67, 68):
                self.assertNotIn((tick, 0), easy)
        modes = report['easy_section_modes']
        self.assertEqual(len(modes), 3)
        self.assertLessEqual(sum(m['mode'] == 'kick_snare' for m in modes), 2)
        self.assertTrue(any(m['mode'] == 'hands' for m in modes))

    def test_pro_cymbal_flags_have_matching_gems_and_no_orphan_dynamics(self):
        tiers, _ = downchart(fixture(), groove() + [(960, 34)], 120)
        for gems in tiers.values():
            for tick, lane in gems:
                if lane in (66, 67, 68):
                    self.assertIn((tick, lane - 64), gems)
                if 34 <= lane <= 37:
                    self.assertIn((tick, lane - 33), gems)
            self.assertFalse(any(40 <= lane <= 44 for _, lane in gems))

    def test_triplet_reduction_uses_pulse_instead_of_alternating_triplets(self):
        expert = [(tick, 1) for tick in range(0, 4 * PPQ, PPQ // 3)]
        tiers, _ = downchart(fixture(120, 1), expert, 120)
        self.assertEqual(times(tiers['Medium'], 1), [0, 960, 1920, 2880])

    def test_odd_and_compound_meter_keep_actual_bar_alignment(self):
        score = fixture(150, 2)
        score['signatures'] = [{'tick': 0, 'numerator': 7, 'denominator': 8},
                               {'tick': 3360, 'numerator': 6, 'denominator': 8}]
        score['end'] = 6240
        expert = []
        for tick in range(0, 6240, 480):
            expert += [(tick, 2), (tick, 66)]
        expert += [(4800, 1)]
        tiers, _ = downchart(score, expert, 150)
        self.assertIn((3360, 2), notes(tiers['Medium']))
        self.assertIn((4800, 2), notes(tiers['Medium']))
        self.assertIn((4800, 1), notes(tiers['Medium']))

    def test_tempo_changes_drive_timekeeping_limits(self):
        score = fixture(120, 2)
        score['tempos'].append({'tick': 3840, 'bpm': 180})
        tiers, _ = downchart(score, groove(2), 120)
        hats = times(tiers['Medium'], 2)
        self.assertEqual([t for t in hats if t < 3840], list(range(0, 3840, 480)))
        self.assertEqual([t for t in hats if t >= 3840], list(range(3840, 7680, 960)))

    def test_sparse_ghost_only_source_gets_review_warning_and_playable_tiers(self):
        tiers, report = downchart(fixture(), [(100, 1), (100, 40)], 120)
        self.assertTrue(report['warnings'])
        for gems in tiers.values():
            self.assertEqual(gems, [(100, 1)])


if __name__ == '__main__':
    unittest.main()
