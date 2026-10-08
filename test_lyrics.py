import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from lyrics import parse_lrc, chart_lyrics, read_lrc
from core import read_gp, export_song, DEFAULT_MAP

class LyricsTests(unittest.TestCase):
    score = {'ppq': 960, 'tempos': [{'tick': 0, 'bpm': 120}, {'tick': 3840, 'bpm': 60}]}

    def test_first_word_uses_line_timestamp(self):
        events, report = chart_lyrics(self.score, parse_lrc('[00:01.00]Hello <00:01.50>world'))
        self.assertIn((1920, 2, 'lyric Hello'), events)
        self.assertIn((2880, 2, 'lyric world'), events)
        self.assertEqual(report['lyric_events'], 2)

    def test_line_and_repeated_timestamps(self):
        events, report = chart_lyrics(self.score, parse_lrc('[ar:Example]\n[00:01.00][00:04.00]Hello world\n[00:06.00]'))
        self.assertIn((1920, 2, 'lyric Hello world'), events)
        self.assertIn((5760, 2, 'lyric Hello world'), events)
        self.assertEqual(report['end_tick'], 7680)

    def test_enhanced_and_explicit_end(self):
        events, report = chart_lyrics(self.score, parse_lrc('[00:01.00]<00:01.00>Hello <00:01.50>world<00:02.00>'))
        self.assertIn((2880, 2, 'lyric world'), events)
        self.assertIn((3840, 0, 'phrase_end'), events)
        self.assertEqual(report['format'], 'enhanced/mixed')

    def test_offset_and_delay(self):
        events, _ = chart_lyrics(self.score, parse_lrc('[offset:100]\n[00:01.00]Hello'), 200, 100)
        self.assertIn((1920, 2, 'lyric Hello'), events)

    def test_utf16(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp)/'lyrics.lrc'
            path.write_text('[00:01.00]Héllo', encoding='utf-16')
            self.assertEqual(read_lrc(path)[0][0]['tokens'][0][1], 'Héllo')

    def test_invalid(self):
        for text in ('Hello', '[00:99.00]Hello', '[00:01.00]Hello\n[00:01.00]World', '[offset:no]\n[00:01.00]Hello'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_lrc(text)

    def test_backward_block_is_evenly_spaced(self):
        phrases, _ = parse_lrc('[00:01.00]First <00:00.50>second <00:00.60>third <00:04.00>fourth')
        self.assertEqual([t for t, _ in phrases[0]['tokens']], [1, 2, 3, 4])
        self.assertEqual(len(phrases[0]['repairs']), 2)

    def test_overrun_keeps_all_words_and_next_line_time(self):
        parsed = parse_lrc('[00:01.00]First <00:05.00>second <00:06.00>third\n[00:04.00]Next')
        self.assertEqual([t for t, _ in parsed[0][0]['tokens']], [1, 2, 3])
        self.assertEqual(parsed[0][0]['end'], 4)
        events, report = chart_lyrics(self.score, parsed)
        self.assertIn((5760, 0, 'phrase_end'), events)
        self.assertIn((5760, 1, 'phrase_start'), events)
        self.assertIn((5760, 2, 'lyric Next'), events)
        self.assertEqual(report['lyric_events'], 4)
        self.assertTrue(report['repairs'])

    def test_explicit_phrase_end_is_shortened(self):
        phrases, _ = parse_lrc('[00:01.00]First <00:06.00>\n[00:04.00]Next')
        self.assertEqual(phrases[0]['end'], 4)
        self.assertEqual(phrases[0]['repairs'][0]['kind'], 'phrase_end_shortened')

    def test_repaired_export_preserves_original_and_writes_review_copy(self):
        score = read_gp(Path(__file__).parent/'demo.gp')
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path = Path(tmp)/'input.lrc'
            source = '[00:01.00]First <00:00.50>second <00:05.00>third\n[00:04.00]Next'
            path.write_text(source, encoding='utf8')
            folder, report = export_song(score, 0, DEFAULT_MAP, Path(tmp)/'songs', lyrics=path)
            self.assertEqual(path.read_text(), source)
            self.assertEqual((folder/'lyrics.lrc').read_bytes(), path.read_bytes())
            repaired = read_lrc(folder/'lyrics_adjusted.lrc')
            self.assertEqual(sum(len(p['tokens']) for p in repaired[0]), 4)
            self.assertFalse(any(p['repairs'] for p in repaired[0]))
            self.assertTrue(report['lyrics']['repairs'])

    def test_negative_clamped(self):
        events, report = chart_lyrics(self.score, parse_lrc('[00:00.00]Hello'), 200)
        self.assertIn((0, 2, 'lyric Hello'), events)
        self.assertIn('clamped', report['warnings'][0])

    def test_export(self):
        score = read_gp(Path(__file__).parent/'demo.gp')
        with TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            path=Path(tmp)/'input.lrc'
            path.write_text('[00:01.00]<00:01.00>Hello <00:01.50>world<00:02.00>',encoding='utf8')
            folder, report=export_song(score,0,DEFAULT_MAP,Path(tmp)/'songs',lyrics=path)
            chart=(folder/'notes.chart').read_text(encoding='utf8')
            self.assertIn('1920 = E "lyric Hello"',chart)
            self.assertIn('2880 = E "lyric world"',chart)
            self.assertIn('lyrics = True',(folder/'song.ini').read_text())
            self.assertEqual((folder/'lyrics.lrc').read_bytes(),path.read_bytes())
            self.assertEqual(report['lyrics']['lyric_events'],2)
