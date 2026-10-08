"""Musical five-fret reduction for GP pitched tracks (not literal MIDI-to-fret mapping)."""
from collections import defaultdict
from math import ceil
from bisect import bisect_right

TRACK_NAMES = {'Guitar': 'Single', 'Bass': 'DoubleBass', 'Rhythm': 'DoubleRhythm'}
INI_NAMES = {'Guitar': 'diff_guitar', 'Bass': 'diff_bass', 'Rhythm': 'diff_rhythm'}

def _time_mapper(score):
    tempos = {round(t['tick']): round(t['bpm'] * 1000) / 1000 for t in score['tempos']}
    tempos.setdefault(0, 120)
    ticks, segments, elapsed, previous, bpm = [], [], 0.0, 0, tempos[0]
    for tick in sorted(tempos):
        if tempos[tick] <= 0:
            raise ValueError('The source contains an invalid tempo.')
        elapsed += (tick - previous) * 60 / (score['ppq'] * bpm)
        ticks.append(tick); segments.append((elapsed, tick, tempos[tick]))
        previous, bpm = tick, tempos[tick]
    def time(tick):
        elapsed, start, bpm = segments[max(0, bisect_right(ticks, tick)-1)]
        return elapsed + (tick-start)*60/(score['ppq']*bpm)
    def tempo(tick):
        return segments[max(0, bisect_right(ticks, tick)-1)][2]
    return time, tempo

def prepare_events(track):
    groups = defaultdict(list)
    # Written attacks avoid rendering a bend/slide as multiple artificial notes.
    source = track.get('chart_notes', track['notes'])
    for note in source:
        tick = round(note['tick'])
        if tick < 0:
            raise ValueError('Negative note positions are unsupported.')
        groups[tick].append(note)
    events = []
    for tick, notes in sorted(groups.items()):
        pitches = sorted({int(n['pitch']) for n in notes})
        events.append({'tick': tick, 'pitches': pitches, 'notes': notes,
                       'length': max(0, round(min(n.get('length', 0) for n in notes))),
                       'hopo': all(n.get('hopo', False) for n in notes),
                       'tap': all(n.get('tap', False) for n in notes),
                       'muted': any(n.get('dead', False) or n.get('palm_mute', False) or n.get('staccato', False) for n in notes),
                       'open': len(pitches) == 1 and all(n.get('fret') == 0 for n in notes)})
    return events

def _window_chunks(events, score, capacity):
    """Reset at rests/sections/chords; split a wide motif into ordered fret windows."""
    sections = {round(s['tick']) for s in score.get('sections', [])}
    chunks, chunk, distinct = [], [], set()
    for event in events:
        pitch = event['pitches'][0]
        separated = chunk and (event['tick'] - chunk[-1]['tick'] - chunk[-1]['length'] > score['ppq'] or
                               any(chunk[-1]['tick'] < s <= event['tick'] for s in sections))
        if len(event['pitches']) > 1 or separated or (pitch not in distinct and len(distinct) >= capacity):
            if chunk: chunks.append(chunk)
            chunk, distinct = [], set()
        if len(event['pitches']) > 1:
            chunks.append([event])
        else:
            chunk.append(event); distinct.add(pitch)
    if chunk: chunks.append(chunk)
    # Balance strictly monotonic scales across windows so a sixth/seventh pitch
    # does not become a lone green note after a full five-note sweep.
    runs = []
    for chunk in chunks:
        if runs and all(len(e['pitches']) == 1 for e in runs[-1] + chunk):
            combined = runs[-1] + chunk
            pitches = [e['pitches'][0] for e in combined]
            ascending = all(a < b for a,b in zip(pitches,pitches[1:]))
            descending = all(a > b for a,b in zip(pitches,pitches[1:]))
            previous = runs[-1][-1]
            separated = chunk[0]['tick']-previous['tick']-previous['length'] > score['ppq'] or any(previous['tick'] < s <= chunk[0]['tick'] for s in sections)
            if (ascending or descending) and not separated:
                runs[-1] = combined
                continue
        runs.append(chunk)
    balanced = []
    for run in runs:
        if len(run) > capacity and all(len(e['pitches']) == 1 for e in run):
            pitches = [e['pitches'][0] for e in run]
            monotonic = all(a < b for a,b in zip(pitches,pitches[1:])) or all(a > b for a,b in zip(pitches,pitches[1:]))
            if monotonic:
                windows = ceil(len(run)/capacity)
                base, extra = divmod(len(run), windows)
                start = 0
                for index in range(windows):
                    size = base + (index < extra)
                    balanced.append(run[start:start+size]); start += size
                continue
        balanced.append(run)
    return balanced

def _melody_chunks(events, score, capacity):
    """Give recurring bars and consecutive riff repeats their own fret windows."""
    if not events:
        return []
    def identity(event):
        return (tuple(event['pitches']), event['length'], event['hopo'],
                event['tap'], event['muted'], event['open'])
    boundaries = {0, len(events)}
    # Repeated bars must not inherit a different pitch palette from neighboring
    # fills or phrases. Include timing and articulation in the match.
    bar_length = 4 * score['ppq']
    bars = defaultdict(list)
    for index, event in enumerate(events):
        bars[event['tick']//bar_length].append(index)
    occurrences = defaultdict(list)
    for indices in bars.values():
        key = tuple((events[i]['tick'] % bar_length, identity(events[i])) for i in indices)
        occurrences[key].append(indices)
    for matches in occurrences.values():
        if len(matches) > 1:
            for indices in matches:
                boundaries.update((indices[0], indices[-1]+1))
    # Also catch wide repeated riffs within/across bars. Matching inter-attack
    # gaps prevents a differently timed fill from being treated as the riff.
    tokens = [(identity(e), events[i+1]['tick']-e['tick'] if i+1 < len(events) else None)
              for i,e in enumerate(events)]
    start = 0
    while start < len(events)-3:
        found = False
        for period in range(2, min(128, (len(events)-start)//2)+1):
            if tokens[start] != tokens[start+period]:
                continue
            first = tokens[start:start+period]
            # The last attack's outgoing gap can differ at the end of a repeat.
            second = tokens[start+period:start+2*period]
            if first[:-1] != second[:-1] or first[-1][0] != second[-1][0]:
                continue
            if len({token[0][0] for token in first}) < 2:
                continue
            end = start+2*period
            while end+period <= len(events):
                following = tokens[end:end+period]
                if following[:-1] != first[:-1] or following[-1][0] != first[-1][0]:
                    break
                end += period
            boundaries.difference_update([b for b in boundaries if start < b < end])
            boundaries.update(range(start, end+1, period))
            start = end
            found = True
            break
        if not found:
            start += 1
    result = []
    ordered = sorted(boundaries)
    for left,right in zip(ordered,ordered[1:]):
        result.extend(_window_chunks(events[left:right], score, capacity))
    return result


def _map(events, score, capacity, max_chord, open_notes=False):
    mapped, resets = [], []
    roots = sorted({e['pitches'][0] for e in events if len(e['pitches']) > 1})
    for chunk in _melody_chunks(events, score, capacity):
        if len(chunk) == 1 and len(chunk[0]['pitches']) > 1:
            event = chunk[0]
            # Octave doublings do not consume extra controller buttons.
            pcs = sorted({p % 12 for p in event['pitches']})
            width = min(max_chord, max(1, len(pcs)))
            root = roots.index(event['pitches'][0])
            start = round(root * (capacity-width) / max(1, len(roots)-1))
            # Power chords use comfortable skipped-fret dyads on Expert/Hard.
            intervals = {(p-event['pitches'][0]) % 12 for p in event['pitches']}
            lanes = (start, start+2) if width == 2 and capacity >= 4 and intervals <= {0, 7} else tuple(range(start, start+width))
            if max(lanes) >= capacity: lanes = tuple(range(capacity-width, capacity))
            mapped.append(dict(event, lanes=lanes))
            continue
        pitches = sorted({e['pitches'][0] for e in chunk})
        # Ordered ranks preserve trills, repeated notes, zigzags and run direction.
        # A one-pitch riff uses green; short phrases use the lower frets.
        rank = {pitch: index for index, pitch in enumerate(pitches)}
        for event in chunk:
            lane = 7 if open_notes and event['open'] else rank[event['pitches'][0]]
            mapped.append(dict(event, lanes=(lane,)))
        resets.append(chunk[0]['tick'])
    return sorted(mapped, key=lambda e: e['tick']), resets

def _reduce(events, score, difficulty):
    _, tempo = _time_mapper(score)
    result = []
    for event in events:
        bpm = tempo(event['tick'])
        spacing = {'Hard': score['ppq']/4 if bpm < 180 else score['ppq']/2,
                   'Medium': score['ppq']/2 if bpm < 140 else score['ppq'],
                   'Easy': score['ppq'] if bpm < 140 else 2*score['ppq']}[difficulty]
        if not result or event['tick']-result[-1]['tick'] >= spacing:
            result.append(event)
    return result

def _serialize(events, ppq, difficulty):
    gems = []
    forced, taps, sustains = 0, 0, 0
    threshold = int(65/192 * ppq)
    for index, event in enumerate(events):
        tick, lanes = event['tick'], event['lanes']
        next_tick = events[index+1]['tick'] if index+1 < len(events) else tick + event['length'] + ppq
        # Shared chord sustain and a 1/16 release gap avoid awkward overlaps.
        length = min(event['length'], max(0, next_tick-tick-round(ppq/4)))
        if event['muted'] or length < ppq/2: length = 0
        gems.extend((tick, lane, length) for lane in lanes)
        sustains += bool(length)
        previous = events[index-1] if index else None
        natural = bool(previous and tick-previous['tick'] <= threshold and len(lanes) == 1 and
                       len(previous['lanes']) == 1 and lanes != previous['lanes'])
        wanted = event['hopo'] and len(lanes) == 1 and difficulty in {'Expert', 'Hard'} and previous is not None
        if event['tap'] and difficulty == 'Expert':
            gems.append((tick, 6, 0)); taps += 1
        elif wanted != natural:
            gems.append((tick, 5, 0)); forced += 1
    return sorted(gems), {'forced_hopo_or_strum': forced, 'taps': taps, 'sustain_positions': sustains}

def chart_fretted(score, track_index, instrument, *, open_notes=False):
    if instrument not in TRACK_NAMES: raise ValueError('Choose Guitar, Bass or Rhythm.')
    track = next((t for t in score['tracks'] if t['index'] == track_index), None)
    if track is None or track['percussion']: raise ValueError(f'{instrument}: choose a pitched track.')
    source = prepare_events(track)
    if not source: raise ValueError(f'{instrument}: the selected track has no notes.')
    events_by_tier = {'Expert': source}
    for difficulty, parent in [('Hard', 'Expert'), ('Medium', 'Hard'), ('Easy', 'Medium')]:
        events_by_tier[difficulty] = _reduce(events_by_tier[parent], score, difficulty)
    sections, counts, preview, resets = [], {}, [], []
    for difficulty, events in events_by_tier.items():
        capacity = {'Expert': 5, 'Hard': 5, 'Medium': 4, 'Easy': 3}[difficulty]
        max_chord = {'Expert': 3, 'Hard': 2, 'Medium': 2, 'Easy': 1}[difficulty]
        mapped, tier_resets = _map(events, score, capacity, max_chord, open_notes and difficulty in {'Expert','Hard'})
        gems, details = _serialize(mapped, score['ppq'], difficulty)
        sections += [f'[{difficulty}{TRACK_NAMES[instrument]}]', '{']
        sections += [f'  {t} = N {lane} {length}' for t, lane, length in gems]
        sections += ['}', '']
        counts[difficulty] = {'positions': len(mapped), 'gems': sum(lane != 5 and lane != 6 for _,lane,_ in gems), **details}
        if difficulty == 'Expert':
            preview = [{'tick': e['tick'], 'source_pitches': e['pitches'], 'lanes': list(e['lanes'])} for e in mapped]
            resets = tier_resets
    time, _ = _time_mapper(score)
    times = [time(e['tick']) for e in source]
    peak = 0; left = 0
    for right, when in enumerate(times):
        while times[left] <= when-5: left += 1
        peak = max(peak, (right-left+1)/5)
    average = len(times)/max(1, times[-1]-times[0])
    intensity = min(6, max(sum(average >= x for x in [1,2,3,4.5,6,8]),
                          sum(peak >= x for x in [1.5,2.5,4,6,8,10])))
    warnings = ['Five-fret conversion is a musical reduction, not a literal representation of every GP pitch/string. Review phrase resets, chords and technique flags against the recording.']
    return '\n'.join(sections), {'track_index': track_index, 'track': track['name'], 'instrument': instrument,
        'source_notes': len(track.get('chart_notes', track['notes'])), 'source_positions': len(source),
        'source_events': track.get('chart_notes', track['notes']),
        'difficulties': counts, 'expert_pattern': preview, 'five_fret_window_starts': resets,
        'chord_policy': 'octave doublings collapsed; maximum three frets; shared sustain; lower tiers reduce chords',
        'intensity': {'estimated': intensity, 'method': 'five-fret density heuristic v1', 'scale': '0–6',
                      'metrics': {'average_positions_per_second': average, 'peak_5s_positions_per_second': peak}},
        'warnings': warnings}
