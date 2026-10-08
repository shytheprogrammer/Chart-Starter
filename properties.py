"""Song metadata validation and an explainable Expert drum intensity estimate."""
import math
from collections import defaultdict
from bisect import bisect_right

TEXT_FIELDS = {'album': 'Album', 'genre': 'Genre', 'year': 'Year', 'charter': 'Charter',
               'icon': 'Song icon', 'loading_phrase': 'Loading text'}
NUMBER_FIELDS = {'album_track': 'Album track', 'playlist_track': 'Playlist position',
                 'preview_start_time': 'Preview start (ms)', 'song_length': 'Song length (ms)',
                 'video_start_time': 'Video start (ms)', 'video_end_time': 'Video end (ms; -1 = full)'}

def validate_properties(values):
    result = {}
    for key, value in (values or {}).items():
        if key not in TEXT_FIELDS and key not in NUMBER_FIELDS and key not in {'modchart','video_loop'}:
            raise ValueError(f'Unsupported song property: {key}')
        value = str(value).strip()
        if not value:
            continue
        if '\n' in value or '\r' in value or '\x00' in value:
            raise ValueError(f'{key} must be a single line of text.')
        if key in NUMBER_FIELDS:
            try:
                number = int(value)
            except ValueError:
                raise ValueError(f'{NUMBER_FIELDS[key]} must be a whole number.')
            if number < 0 and key not in {'video_start_time','video_end_time'}:
                raise ValueError(f'{NUMBER_FIELDS[key]} cannot be negative.')
            if key == 'video_end_time' and number < -1:
                raise ValueError('Video end must be -1 or a nonnegative millisecond value.')
            value = str(number)
        if key in {'modchart','video_loop'}:
            if value.lower() not in {'true', 'false'}:
                raise ValueError(f'{key} must be True or False.')
            value = value.title()
        result[key] = value
    result.setdefault('charter', 'Chart Starter')
    return result

def estimate_intensity(score, gems):
    """Heuristic 0–6 rating, not an official or universal Clone Hero formula."""
    tempos = {round(t['tick']): round(t['bpm'] * 1000) / 1000 for t in score['tempos']}
    tempos.setdefault(0, 120)
    starts, segments, elapsed, previous, bpm = [], [], 0.0, 0, tempos[0]
    for tick in sorted(tempos):
        elapsed += (tick - previous) * 60 / (score['ppq'] * bpm)
        starts.append(tick)
        segments.append((elapsed, tick, tempos[tick]))
        previous, bpm = tick, tempos[tick]
    def seconds(tick):
        elapsed, start, tempo = segments[max(0, bisect_right(starts, tick) - 1)]
        return elapsed + (tick - start) * 60 / (score['ppq'] * tempo)
    groups = defaultdict(set)
    for tick, lane in gems:
        if lane in {0, 1, 2, 3, 4, 32}:
            groups[tick].add(lane)
    hits = sorted(seconds(t) for t, lanes in groups.items() for _ in lanes)
    kicks = sorted(seconds(t) for t, lanes in groups.items() if lanes & {0, 32})
    def peak(times, window):
        left, highest = 0, 0
        for right, time in enumerate(times):
            while times[left] <= time - window:
                left += 1
            highest = max(highest, right - left + 1)
        return highest / window
    duration = max(1.0, hits[-1] - hits[0]) if hits else 1.0
    average = len(hits) / duration
    peak5, sustained10, kick5 = peak(hits, 5), peak(hits, 10), peak(kicks, 5)
    coordination = sum(len(lanes) >= 3 for lanes in groups.values()) / max(1, len(groups))
    def tier(value, thresholds):
        return sum(value >= threshold for threshold in thresholds)
    # Density counts playable hits, excluding cymbal/dynamic marker events.
    base = max(tier(sustained10, [1.5, 2.5, 4, 5.5, 7.5, 10]),
               tier(average, [1.5, 2.5, 4, 5.5, 7.5, 10]))
    burst = tier(peak5, [2, 3.5, 5, 7, 9, 12])
    pedal = tier(kick5, [0.8, 1.4, 2, 3, 4, 6])
    rating = min(6, max(base, burst - 1, pedal))
    if coordination >= 0.15 and rating < 6:
        rating += 1
    return {'estimated': rating, 'scale': '0–6', 'method': 'Expert drum heuristic v1',
            'metrics': {'average_hits_per_second': round(average, 3),
                        'peak_5s_hits_per_second': round(peak5, 3),
                        'peak_10s_hits_per_second': round(sustained10, 3),
                        'peak_5s_kicks_per_second': round(kick5, 3),
                        'three_limb_fraction': round(coordination, 3)},
            'note': 'Estimated from Expert playable hits, tempo changes, sustained density, bursts, kick speed and coordination. Human review is recommended; no universal official formula is published.'}

def chosen_intensity(estimate, override):
    if override is None or str(override).strip() == '':
        return dict(estimate, selected=estimate['estimated'], overridden=False)
    try:
        value = int(str(override))
    except ValueError:
        raise ValueError('Intensity override must be a whole number from 0 to 6.')
    if not 0 <= value <= 6:
        raise ValueError('Intensity override must be from 0 to 6.')
    return dict(estimate, selected=value, overridden=True)

def song_intensity(instruments, override=None):
    if not instruments:
        raise ValueError('Select at least one instrument to calculate song difficulty.')
    components = {role: {'estimated': details['intensity']['estimated'],
                         'selected': details['intensity']['selected']} for role,details in instruments.items()}
    estimated = sum(c['estimated'] for c in components.values())/len(components)
    selected = sum(c['selected'] for c in components.values())/len(components)
    # Round half up rather than Python's banker's rounding for the displayed tier.
    result = chosen_intensity({'estimated': math.floor(estimated+0.5), 'average_estimated': estimated,
                               'average_selected': selected, 'components': components,
                               'method': 'Arithmetic mean of selected instrument Expert intensities; rounded half up to 0–6.'}, override)
    if not result['overridden']:
        result['selected'] = math.floor(selected+0.5)
    return result
