"""Local Guitar Pro score import and audited Clone Hero chart export."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from collections import Counter, defaultdict
from downchart import downchart
from lyrics import read_lrc, chart_lyrics, adjusted_lrc
from properties import validate_properties, estimate_intensity, chosen_intensity, song_intensity
from fretted import chart_fretted, INI_NAMES
from star_power import add_star_power
from extras import validate_extras, package_extras, AUDIO
from branding import APP_NAME, RELEASE_VERSION


ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
LANES = {'Kick': (0, False), 'Snare / red': (1, False), 'High tom / yellow': (2, False),
         'Mid tom / blue': (3, False), 'Low tom / green': (4, False),
         'Hi-hat / yellow cymbal': (2, True), 'Ride / blue cymbal': (3, True),
         'Crash / green cymbal': (4, True), 'Ignore': None}
DEFAULT_MAP = {35: 'Kick', 36: 'Kick', 37: 'Snare / red', 38: 'Snare / red', 40: 'Snare / red',
               41: 'Low tom / green', 43: 'Low tom / green', 45: 'Mid tom / blue',
               47: 'Mid tom / blue', 48: 'High tom / yellow', 50: 'High tom / yellow',
               42: 'Hi-hat / yellow cymbal', 46: 'Hi-hat / yellow cymbal',
               49: 'Crash / green cymbal', 52: 'Crash / green cymbal', 55: 'Crash / green cymbal',
               57: 'Crash / green cymbal', 51: 'Ride / blue cymbal', 53: 'Ride / blue cymbal',
               59: 'Ride / blue cymbal'}
PITCH_NAMES = {35: 'Acoustic kick', 36: 'Kick', 37: 'Side stick', 38: 'Snare', 40: 'Electric snare',
               41: 'Low floor tom', 42: 'Closed hi-hat', 43: 'High floor tom', 44: 'Pedal hi-hat',
               45: 'Low tom', 46: 'Open hi-hat', 47: 'Low-mid tom', 48: 'High-mid tom',
               49: 'Crash 1', 50: 'High tom', 51: 'Ride 1', 52: 'China', 53: 'Ride bell',
               54: 'Tambourine', 55: 'Splash', 56: 'Cowbell', 57: 'Crash 2', 59: 'Ride 2'}


class AppError(Exception):
    pass


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:100] or 'Untitled'
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        value = '_' + value
    return value


def unique_path(parent: Path, name: str) -> Path:
    target = parent / name
    n = 2
    while target.exists():
        p = Path(name)
        target = parent / f'{p.stem} ({n}){p.suffix}'
        n += 1
    return target


def read_gp(path: Path) -> dict:
    node = ROOT / 'vendor' / 'node.exe'
    executable = str(node) if node.exists() else shutil.which('node')
    if not executable:
        raise AppError('Node.js is needed to read Guitar Pro files. Install Node.js or use the bundled Windows app.')
    if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise AppError('Choose a Guitar Pro file smaller than 64 MB.')
    try:
        result = subprocess.run([executable, str(ROOT / 'gp_bridge.cjs'), str(path.resolve())],
                                capture_output=True, text=True, encoding='utf8', timeout=120,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AppError(f'Could not read the file: {e}') from e
    if result.returncode:
        raise AppError(result.stderr.strip()[-1500:] or 'Could not read the Guitar Pro file.')
    try:
        score = json.loads(result.stdout)
        if not score['tracks']:
            raise AppError('This file has no tracks.')
        return score
    except (ValueError, KeyError) as e:
        raise AppError('The Guitar Pro reader returned an invalid score.') from e


def _quoted(text) -> str:
    return str(text).replace('\\', '/').replace('"', "'").replace('\n', ' ').replace('\r', ' ')


def duration_seconds(score: dict) -> float:
    end = max([score.get('end', 0)] + [n['tick'] + n.get('length', 0) for t in score['tracks'] for n in t['notes']])
    tempos = {int(round(t['tick'])): float(t['bpm']) for t in score['tempos']}
    tempos.setdefault(0, 120)
    current, bpm, seconds = 0, tempos[0], 0.0
    for tick in sorted(tempos):
        if tick > end:
            break
        seconds += (tick - current) / score['ppq'] * 60 / bpm
        current, bpm = tick, tempos[tick]
    return seconds + (end - current) / score['ppq'] * 60 / bpm


def double_bass_ticks(score: dict, ticks: list[int], song_bpm: float) -> tuple[set[int], list[dict]]:
    """Above 110 BPM, alternate kicks in runs with gaps <= a sixteenth note."""
    if not math.isfinite(song_bpm) or song_bpm <= 0:
        raise AppError('Enter a positive, finite song BPM.')
    if song_bpm <= 110:
        return set(), []
    tagged, runs, run = set(), [], []
    max_gap = score['ppq'] / 4

    def finish():
        if len(run) >= 2:
            alternate = run[1::2]
            tagged.update(alternate)
            runs.append({'start_tick': run[0], 'end_tick': run[-1], 'kick_count': len(run),
                         'double_bass_ticks': alternate})

    for tick in sorted(set(ticks)):
        if run and tick - run[-1] > max_gap:
            finish()
            run = []
        run.append(tick)
    finish()
    return tagged, runs


def convert(score: dict, track_index: int, mapping: dict[int, str], *, strict=True,
            dynamics=False, title='', artist='', audio_name='song.wav',
            song_bpm=None, lyrics=None, offset_ms=0, lyrics_offset_ms=0) -> tuple[str, dict]:
    track = next((t for t in score['tracks'] if t['index'] == track_index), None)
    if track is None or not track['percussion']:
        raise AppError('Select a percussion track.')
    if not track['notes']:
        raise AppError('This percussion track has no playable notes.')
    groups = defaultdict(list)
    ignored, unmapped, rounded = Counter(), Counter(), 0
    source_counts = Counter(n['pitch'] for n in track['notes'])
    for n in track['notes']:
        pitch = n['pitch']
        selection = mapping.get(pitch)
        if selection not in LANES:
            unmapped[pitch] += 1
            continue
        lane = LANES[selection]
        if lane is None:
            ignored[pitch] += 1
            continue
        tick = int(round(n['tick']))
        if tick < 0:
            raise AppError('The source contains negative playback ticks.')
        rounded += abs(n['tick'] - tick) > 0.00001
        groups[tick, lane[0]].append((lane[1], n))
    collisions = [{'tick': tick, 'lane': lane, 'pitches': [n['pitch'] for _, n in items],
                   'hits': len(items)} for (tick, lane), items in sorted(groups.items()) if len(items) > 1]
    issues = []
    if unmapped:
        issues.append('Unmapped pitches: ' + ', '.join(f'{p} ({c} hits)' for p, c in unmapped.items()))
    if collisions:
        issues.append(f'{len(collisions)} simultaneous same-lane collisions (Clone Hero cannot represent every hit).')
    if rounded:
        issues.append(f'{rounded} hit positions required rounding to the nearest source-resolution tick.')
    if strict and issues:
        raise AppError('\n'.join(issues) + '\nAdjust the mapping, or turn off strict export to accept a documented approximation.')
    if not groups:
        raise AppError('No hits remain after mapping.')
    if song_bpm is None:
        song_bpm = next((t['bpm'] for t in score['tempos'] if t['tick'] == 0), 120)
    double_kicks, kick_runs = double_bass_ticks(score, [tick for tick, lane in groups if lane == 0], song_bpm)
    gems = []
    for (tick, lane), items in sorted(groups.items()):
        cymbal = any(c for c, _ in items)
        gems.append((tick, 32 if lane == 0 and tick in double_kicks else lane))
        if cymbal:
            gems.append((tick, 64 + lane))
        ghost = any(n.get('ghost', False) for _, n in items)
        accent = any(n.get('accent', False) for _, n in items)
        if lane and (ghost or accent):
            gems.append((tick, (33 if accent else 39) + lane))
        elif dynamics and lane:
            velocity = max(n['velocity'] for _, n in items)
            if velocity < 50:
                gems.append((tick, 39 + lane))
            elif velocity >= 115:
                gems.append((tick, 33 + lane))
    title, artist = title or score.get('title') or 'Untitled', artist or score.get('artist') or 'Unknown artist'
    lines, lyric_report = chart_header(score, title, artist, audio_name, lyrics, offset_ms, lyrics_offset_ms, max(t for t, _ in groups))
    lines += ['[ExpertDrums]', '{']
    lines += [f'  {tick} = N {lane} 0' for tick, lane in sorted(gems)]
    lines += ['}', '']
    lower_tiers, reductions = downchart(score, gems, song_bpm)
    for difficulty, tier_gems in lower_tiers.items():
        lines += [f'[{difficulty}Drums]', '{']
        lines += [f'  {tick} = N {lane} 0' for tick, lane in tier_gems]
        lines += ['}', '']
    report = {'title': title, 'artist': artist, 'track': track['name'], 'ppq': score['ppq'],
              'source_hits': len(track['notes']), 'exported_hits': len(groups),
              'unmapped': dict(unmapped), 'ignored': dict(ignored), 'collisions': collisions,
              'rounded_hits': rounded, 'issues': issues, 'source_pitch_counts': dict(source_counts),
              'playback_tick_shift': score.get('tickShift', 0),
              'mapping': mapping, 'techniques_in_written_score': track.get('techniques', {}),
              'velocity_dynamics': dynamics, 'duration_seconds': duration_seconds(score),
              'source_events': track['notes'],
              'downchart': reductions, 'lyrics': lyric_report, 'intensity': estimate_intensity(score, gems),
              'double_bass': {'song_bpm': song_bpm, 'bpm_cutoff_exclusive': 110,
                              'maximum_gap_ticks': score['ppq'] / 4, 'minimum_run_hits': 2, 'tagged_hits': len(double_kicks),
                              'runs': kick_runs},
              'notes': ['Hit times come from alphaTab playback, including repeats, tuplets and grace notes.',
                        'Different drum pitches mapped to one lane lose their instrument distinction.',
                        'Hi-hat openness, cymbal bell/edge/choke and continuous velocities are not separate Pro Drums gems.',
                        'Flams and rolls follow alphaTab playback expansion; review against the source.',
                        'Written ghost/accent flags are preserved when matched to playback hits.',
                        'Qualifying fast kick runs alternate normal kick (0) and 2x Kick (32), starting with normal kick.',
                        'Velocity dynamics for otherwise unmarked notes are optional estimates: ghost <50, accent >=115.']}
    return '\n'.join(lines), report


def chart_header(score, title='', artist='', audio_name='song.wav', lyrics=None, offset_ms=0, lyrics_offset_ms=0, last_tick=0):
    title, artist = title or score.get('title') or 'Untitled', artist or score.get('artist') or 'Unknown artist'
    lines = ['[Song]', '{', f'  Name = "{_quoted(title)}"', f'  Artist = "{_quoted(artist)}"',
             '  Charter = "Chart Starter"', '  Offset = 0', f"  Resolution = {score['ppq']}",
             f'  MusicStream = "{_quoted(audio_name)}"', '}', '[SyncTrack]', '{']
    sync = []
    tempos = {int(round(t['tick'])): t['bpm'] for t in score['tempos']}
    tempos.setdefault(0, 120)
    for tick, bpm in tempos.items():
        if not math.isfinite(bpm) or bpm <= 0:
            raise AppError('The source contains an invalid tempo.')
        sync.append((tick, f'B {round(bpm * 1000)}'))
    signatures = {int(round(s['tick'])): s for s in score['signatures']}
    signatures.setdefault(0, {'numerator': 4, 'denominator': 4})
    for tick, sig in signatures.items():
        denominator = sig['denominator']
        if denominator <= 0 or denominator & (denominator - 1):
            raise AppError('The time signature denominator is unsupported.')
        sync.append((tick, f"TS {sig['numerator']} {int(math.log2(denominator))}"))
    lines += [f'  {tick} = {event}' for tick, event in sorted(sync)]
    lyric_events, lyric_report = [], None
    if lyrics is not None:
        try:
            lyric_events, lyric_report = chart_lyrics(score, lyrics, offset_ms, lyrics_offset_ms)
        except ValueError as e:
            raise AppError(str(e)) from e
    lines += ['}', '[Events]', '{']
    global_events = [(round(section['tick']), 3, 'section ' + str(section['name']))
                     for section in score.get('sections', [])]
    end = max(round(score.get('end', 0)), last_tick + 1)
    for tick, _, event in sorted(global_events + lyric_events):
        lines.append(f'  {tick} = E "{_quoted(event)}"')
    if lyric_report:
        end = max(end, lyric_report['end_tick'] + 1)
    lines += [f'  {end} = E "end"', '}']
    return lines, lyric_report



def write_silence(path: Path, seconds: float):
    if not math.isfinite(seconds) or not 0 < seconds <= 6 * 3600:
        raise AppError('The silent practice track must be between 0 and 6 hours.')
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(8000)
        count = math.ceil(seconds * 8000)
        block = b'\0' * 16000
        while count:
            take = min(count, 8000)
            f.writeframesraw(block[:take * 2])
            count -= take


def convert_song(score, track_index, mapping, *, fretted_tracks=None, intensity_override=None,
                 song_intensity_override=None, star_power_enabled=True, **options):
    """One shared timeline with optional drums and any selected five-fret roles."""
    instruments = {}
    if track_index is not None:
        chart, report = convert(score, track_index, mapping, **options)
        report['intensity'] = chosen_intensity(report['intensity'], intensity_override)
        instruments['Drums'] = {'track_index': track_index, 'track': report['track'],
                                'intensity': report['intensity'], 'difficulties': report['downchart']['difficulties']}
    else:
        title, artist = options.get('title') or score.get('title') or 'Untitled', options.get('artist') or score.get('artist') or 'Unknown artist'
        last_tick = max([0] + [round(n['tick']) for t in score['tracks'] for n in t['notes']])
        lines, lyric_report = chart_header(score, title, artist, options.get('audio_name', 'song.wav'),
            options.get('lyrics'), options.get('offset_ms', 0), options.get('lyrics_offset_ms', 0), last_tick)
        chart = '\n'.join(lines) + '\n'
        report = {'title': title, 'artist': artist, 'source_hits': 0, 'exported_hits': 0,
                  'issues': [], 'ignored': {}, 'duration_seconds': duration_seconds(score), 'lyrics': lyric_report,
                  'double_bass': {'tagged_hits': 0}, 'downchart': {'warnings': [], 'difficulties': {}},
                  'intensity': {'estimated': 0, 'selected': 0, 'overridden': False}}
    for role, selection in (fretted_tracks or {}).items():
        part, details = chart_fretted(score, selection['track_index'], role, open_notes=selection.get('open_notes', False))
        details['intensity'] = chosen_intensity(details['intensity'], selection.get('intensity_override'))
        chart += '\n' + part
        instruments[role] = details
    if not instruments:
        raise AppError('Select at least one instrument to export.')
    report['instruments'] = instruments
    report['application'] = {'name': APP_NAME, 'version': RELEASE_VERSION}
    report['song_intensity'] = song_intensity(instruments, song_intensity_override)
    if star_power_enabled:
        chart, report['star_power'] = add_star_power(chart, score)
    else:
        report['star_power'] = {'enabled': False, 'instruments': {}}
    return chart, report


def export_song(score: dict, track_index: int, mapping: dict, parent: Path, *, audio: Path | None = None,
                offset_ms=0, strict=True, dynamics=False, title='', artist='',
                song_bpm=None, lyrics: Path | None = None, lyrics_offset_ms=0,
                properties=None, intensity_override=None, album_art: Path | None = None,
                fretted_tracks=None, extras=None, song_intensity_override=None,
                star_power_enabled=True) -> tuple[Path, dict]:
    try:
        metadata = validate_properties(properties)
        media = validate_extras(extras)
    except ValueError as e:
        raise AppError(str(e)) from e
    if album_art and (not album_art.is_file() or album_art.suffix.lower() not in {'.png', '.jpg', '.jpeg'}):
        raise AppError('Choose an existing PNG or JPG album image.')
    if audio and (not audio.is_file() or audio.suffix.lower() not in AUDIO):
        raise AppError('Choose an existing OGG, OPUS, MP3 or WAV audio file.')
    try:
        parsed_lyrics = read_lrc(lyrics) if lyrics else None
    except (ValueError, OSError) as e:
        raise AppError(str(e)) from e
    audio_name = 'song' + (audio.suffix.lower() if audio else '.wav')
    try:
        chart, report = convert_song(score, track_index, mapping, strict=strict, dynamics=dynamics,
                                    title=title, artist=artist, audio_name=audio_name,
                                    song_bpm=song_bpm, lyrics=parsed_lyrics, offset_ms=offset_ms, lyrics_offset_ms=lyrics_offset_ms,
                                    fretted_tracks=fretted_tracks, intensity_override=intensity_override,
                                    song_intensity_override=song_intensity_override, star_power_enabled=star_power_enabled)
    except ValueError as e:
        raise AppError(str(e)) from e
    report['audio'] = 'User-provided recording' if audio else 'Silent practice placeholder'
    report['offset_ms'] = offset_ms
    report['song_properties'] = metadata
    report['album_art'] = album_art.name if album_art else None
    if 'Song icon image' in media:
        metadata['icon'] = media['Song icon image'].stem
    if album_art:
        metadata['cover'] = 'album.png' if album_art.suffix.lower() == '.png' else 'album.jpg'
    if 'Photo background' in media:
        extension = media['Photo background'].suffix.lower()
        metadata['background'] = 'background' + ('.jpg' if extension == '.jpeg' else extension)
    if 'Video background' in media:
        metadata['video'] = 'video' + media['Video background'].suffix.lower()
    chart = chart.replace('  Charter = "Chart Starter"', f'  Charter = "{_quoted(metadata["charter"])}"', 1)
    stream_keys = {'Guitar stem': 'GuitarStream', 'Bass stem': 'BassStream', 'Rhythm stem': 'RhythmStream',
                   'Drums stem': 'DrumStream', 'Kick / drums_1 stem': 'DrumStream',
                   'Snare / drums_2 stem': 'Drum2Stream', 'Toms / drums_3 stem': 'Drum3Stream', 'Cymbals / drums_4 stem': 'Drum4Stream'}
    from extras import EXTRA_TYPES
    streams = [f'  {stream_keys[role]} = "{EXTRA_TYPES[role][1]}{path.suffix.lower()}"' for role,path in media.items() if role in stream_keys]
    if streams:
        head, tail = chart.split('}',1)
        chart = head + '\n'.join(streams) + '\n}' + tail
    parent.mkdir(parents=True, exist_ok=True)
    target = unique_path(parent, safe_name(f"{report['artist']} - {report['title']}"))
    stage = Path(tempfile.mkdtemp(prefix='.chart-starter-', dir=parent))
    try:
        report['extras'] = package_extras(stage, media)
        (stage / 'notes.chart').write_text(chart, encoding='utf8')
        intensity = report['intensity']['selected']
        ini = f"[song]\nname = {_quoted(report['title'])}\nartist = {_quoted(report['artist'])}\ndelay = {offset_ms}\n"
        ini += f"diff_band = {report['song_intensity']['selected']}\n"
        if 'Drums' in report['instruments']:
            ini += f'pro_drums = True\nfive_lane_drums = False\ndiff_drums = {intensity}\ndiff_drums_real = {intensity}\n'
        for role, details in report['instruments'].items():
            if role in INI_NAMES:
                ini += f"{INI_NAMES[role]} = {details['intensity']['selected']}\n"
        ini += ''.join(f'{key} = {value}\n' for key, value in metadata.items())
        if album_art:
            shutil.copyfile(album_art, stage / ('album.png' if album_art.suffix.lower() == '.png' else 'album.jpg'))
        if lyrics:
            ini += 'lyrics = True\n'
            shutil.copyfile(lyrics, stage / 'lyrics.lrc')
            if report['lyrics']['repairs']:
                (stage / 'lyrics_adjusted.lrc').write_text(adjusted_lrc(parsed_lyrics), encoding='utf8')
            report['lyrics']['source_file'] = lyrics.name
        (stage / 'song.ini').write_text(ini, encoding='utf8')
        (stage / 'conversion_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
        if audio:
            shutil.copyfile(audio, stage / audio_name)
        else:
            write_silence(stage / audio_name, max(report['duration_seconds'], (report['lyrics'] or {}).get('audio_end_seconds', 0)) + abs(offset_ms) / 1000 + 3)
        stage.rename(target)
    except Exception:
        shutil.rmtree(stage)
        raise
    return target, report
