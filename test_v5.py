import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from properties import song_intensity
from star_power import add_star_power, bar_grid, SECTION, NOTE
from core import read_gp, convert_song, export_song, DEFAULT_MAP, AppError
from extras import validate_extras

ROOT = Path(__file__).parent

class StarPowerTests(unittest.TestCase):
    def test_every_instrument_and_tier_has_playable_nonoverlapping_phrases(self):
        score = read_gp(ROOT/'demo.gp')
        fretted = read_gp(ROOT/'demo-fretted.gp')['tracks']
        for index,track in enumerate(fretted,1): track['index'] = index
        score['tracks'].extend(fretted)
        chart, report = convert_song(score, 0, DEFAULT_MAP,
            fretted_tracks={role:{'track_index':index} for index,role in enumerate(('Guitar','Bass','Rhythm'),1)})
        self.assertEqual(len(report['star_power']['instruments']),4)
        for match in SECTION.finditer(chart):
            playable = {0,1,2,3,4,32} if match[2]=='Drums' else {0,1,2,3,4,7}
            ticks = [int(t) for t,l,_ in NOTE.findall(match[3]) if int(l) in playable]
            phrases = [(int(t),int(length)) for t,length in re.findall(r'(\d+) = S 2 (\d+)',match[3])]
            self.assertTrue(phrases)
            for start,length in phrases:
                self.assertGreater(length,0)
                self.assertTrue(any(start <= t < start+length for t in ticks))
            self.assertTrue(all(a+l <= b for (a,l),(b,_) in zip(phrases,phrases[1:])))

    def test_long_chart_distribution_and_idempotence(self):
        score = {'ppq':960,'end':32*3840,'bars':[],'signatures':[],'sections':[]}
        notes = '\n'.join(f'{t} = N 0 0' for t in range(0,32*3840,960))
        chart = '[ExpertSingle]\n{\n'+notes+'\n}'
        updated, report = add_star_power(chart,score)
        phrases = report['instruments']['Guitar']['Expert']['phrases']
        self.assertEqual(len(phrases),4)
        self.assertTrue(all(p['length'] <= 2*3840 for p in phrases))
        self.assertEqual(add_star_power(updated,score)[0], updated)

    def test_odd_meter_bar_grid(self):
        bars = bar_grid({'ppq':960,'bars':[],'signatures':[{'tick':0,'numerator':7,'denominator':8},{'tick':6720,'numerator':3,'denominator':4}]},10000)
        self.assertEqual(bars[:3],[(0,3360),(3360,6720),(6720,9600)])

    def test_single_note_sparse_tier_has_phrase_and_warning(self):
        chart, report = add_star_power('[EasySingle]\n{\n0 = N 0 0\n}',{'ppq':960,'end':960})
        self.assertIn('0 = S 2 1',chart)
        self.assertTrue(report['instruments']['Guitar']['Easy']['warnings'])

    def test_disable_does_not_add_markers(self):
        score = read_gp(ROOT/'demo.gp')
        chart,report=convert_song(score,0,DEFAULT_MAP,star_power_enabled=False)
        self.assertNotIn(' = S 2 ',chart)
        self.assertFalse(report['star_power']['enabled'])

class SongRatingTests(unittest.TestCase):
    def test_mean_uses_only_selected_parts_and_rounds_half_up(self):
        rating=song_intensity({'Drums':{'intensity':{'estimated':1,'selected':4}},'Guitar':{'intensity':{'estimated':2,'selected':3}}})
        self.assertEqual(rating['average_estimated'],1.5)
        self.assertEqual(rating['estimated'],2)
        self.assertEqual(rating['average_selected'],3.5)
        self.assertEqual(rating['selected'],4)
        self.assertEqual(len(rating['components']),2)

    def test_song_override_keeps_component_ratings(self):
        rating=song_intensity({'Bass':{'intensity':{'estimated':6,'selected':5}}},0)
        self.assertEqual(rating['selected'],0)
        self.assertEqual(rating['average_selected'],5)
        self.assertTrue(rating['overridden'])

    def test_no_selected_instruments_rejected(self):
        with self.assertRaises(ValueError):song_intensity({})

class ExtrasTests(unittest.TestCase):
    def test_song_media_custom_bundle_stems_and_average_export(self):
        score=read_gp(ROOT/'demo-fretted.gp')
        with TemporaryDirectory(dir=ROOT) as tmp:
            parent=Path(tmp)
            extras={}
            for role,name in [('Photo background','photo.jpeg'),('Video background','clip.webm'),('Preview audio','preview.opus'),('Guitar stem','guitar.ogg'),('Highway image','highway.png'),('Highway video','animated.webm'),('Highway video config','config.ini'),('Song icon image','my-icon.png'),('Color profile','colors.ini')]:
                p=parent/name;p.write_bytes(b'copy verification');extras[role]=p
            selections={role:{'track_index':index,'intensity_override':value} for index,(role,value) in enumerate([('Guitar',2),('Bass',4),('Rhythm',6)])}
            folder,report=export_song(score,None,{},parent/'songs',fretted_tracks=selections,extras=extras)
            for name in ['background.jpg','video.webm','preview.opus','guitar.ogg','Extras/Custom/Highways/highway.png','Extras/Custom/Video Highways/Chart highway/highway.webm','Extras/Custom/Video Highways/Chart highway/config.ini','Extras/Custom/Game Icons/my-icon.png','Extras/Custom/Colors/colors.ini','Extras/INSTALL.txt']:
                self.assertTrue((folder/name).is_file(),name)
            self.assertEqual((folder/'video.webm').read_bytes(),(parent/'clip.webm').read_bytes())
            ini=(folder/'song.ini').read_text()
            self.assertIn('diff_band = 4',ini)
            self.assertIn('icon = my-icon',ini)
            self.assertIn('video = video.webm',ini)
            self.assertIn('background = background.jpg',ini)
            self.assertIn('GuitarStream = "guitar.ogg"',(folder/'notes.chart').read_text())
            self.assertEqual(report['song_intensity']['average_selected'],4)
            self.assertEqual(len(report['extras']['files']),9)

    def test_invalid_extras_and_conflicting_drums_rejected(self):
        with TemporaryDirectory(dir=ROOT) as tmp:
            path=Path(tmp)/'test.ogg';path.write_bytes(b'copy verification')
            for extras in ({'Unknown':path},{'Video background':path},{'Drums stem':path,'Kick / drums_1 stem':path}):
                with self.assertRaises(ValueError):validate_extras(extras)

    def test_invalid_video_creates_no_output(self):
        score=read_gp(ROOT/'demo.gp')
        with TemporaryDirectory(dir=ROOT) as tmp:
            parent=Path(tmp)/'songs'
            with self.assertRaises(AppError):export_song(score,0,DEFAULT_MAP,parent,extras={'Video background':Path(tmp)/'missing.mp4'})
            self.assertFalse(parent.exists())
