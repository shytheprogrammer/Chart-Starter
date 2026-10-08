"""Distributed, note-containing Star Power phrases on a shared musical bar grid."""
import re
from bisect import bisect_left

INSTRUMENTS = {'Drums': 'Drums', 'Single': 'Guitar', 'DoubleBass': 'Bass', 'DoubleRhythm': 'Rhythm'}
SECTION = re.compile(r'\[(Expert|Hard|Medium|Easy)(Drums|Single|DoubleBass|DoubleRhythm)\]\s*\{([^}]*)\}', re.S)
NOTE = re.compile(r'^\s*(\d+)\s*=\s*N\s+(\d+)\s+(\d+)\s*$', re.M)

def bar_grid(score, end):
    bars = sorted({(round(b['tick']), round(b['end'])) for b in score.get('bars', []) if b['end'] > b['tick']})
    if bars and bars[-1][1] >= end:
        return bars
    # Scores without a playback bar lookup still respect time signature changes.
    signatures = {round(s['tick']): s for s in score.get('signatures', [])}
    signatures.setdefault(0, {'numerator': 4, 'denominator': 4})
    ticks = sorted(signatures)
    fallback, current, signature_index = [], 0, 0
    while current < max(1, end):
        while signature_index+1 < len(ticks) and ticks[signature_index+1] <= current: signature_index += 1
        sig = signatures[ticks[signature_index]]
        length = max(1, round(score['ppq']*sig['numerator']*4/sig['denominator']))
        next_change = ticks[signature_index+1] if signature_index+1 < len(ticks) else current+length
        following = min(current+length, next_change)
        fallback.append((current, following)); current = following
    return bars + [b for b in fallback if not bars or b[0] >= bars[-1][1]]

def _phrases(notes, windows, ppq):
    ticks = sorted(notes)
    result, warnings = [], []
    for left, right in windows:
        candidates = ticks[bisect_left(ticks, left):bisect_left(ticks, right)]
        if not candidates: continue
        # Avoid rewarding a phrase that spans a long instrumental rest.
        clusters, cluster = [], []
        for tick in candidates:
            if cluster and tick-cluster[-1] > 2*ppq:
                clusters.append(cluster); cluster = []
            cluster.append(tick)
        if cluster: clusters.append(cluster)
        cluster = max(clusters, key=lambda group: (len(group), -group[0]))
        start, last = cluster[0], cluster[-1]
        end = min(right, max(last+1, last+notes[last]))
        if result and start < result[-1]['end_tick']: continue
        result.append({'start_tick': start, 'end_tick': end, 'length': end-start, 'note_positions': len(cluster)})
        if len(cluster) == 1:
            warnings.append('A sparse/short phrase contains one playable note position; review it in game.')
    if not result and ticks:
        # Even a very short or heavily reduced difficulty gets an earnable phrase.
        start = ticks[0]
        end = max(start+1, start+notes[start])
        result.append({'start_tick': start, 'end_tick': end, 'length': end-start, 'note_positions': 1})
        warnings.append('Only a short fallback phrase could be placed; review this difficulty in game.')
    return result, sorted(set(warnings))

def add_star_power(chart, score):
    matches = list(SECTION.finditer(chart))
    notes_by_section = {}
    for match in matches:
        playable = {0,1,2,3,4,32} if match[2] == 'Drums' else {0,1,2,3,4,7}
        notes = {}
        for tick, lane, length in NOTE.findall(match[3]):
            if int(lane) in playable:
                tick, length = int(tick), int(length)
                notes[tick] = max(notes.get(tick, 0), length)
        notes_by_section[match[1]+match[2]] = notes
    end = max([round(score.get('end', 0))] + [t+length+1 for notes in notes_by_section.values() for t,length in notes.items()])
    bars = bar_grid(score, end)
    schedules = {}
    for suffix in INSTRUMENTS:
        expert = notes_by_section.get('Expert'+suffix, {})
        ticks = sorted(expert)
        active = [index for index,(left,right) in enumerate(bars) if bisect_left(ticks,right) > bisect_left(ticks,left)]
        windows = []
        # Two-bar rewards, roughly one per eight active bars. Musical section
        # boundaries stop phrases from drifting into the next section.
        sections = sorted(round(s['tick']) for s in score.get('sections', []))
        for slot in range(0, len(active), 8):
            index = active[slot]
            left, right = bars[index][0], bars[min(index+1,len(bars)-1)][1]
            boundary = next((s for s in sections if left < s < right), None)
            if boundary is not None: right = boundary
            windows.append((left,right))
        schedules[suffix] = windows
    reports = {}
    def replace(match):
        difficulty, suffix, body = match[1], match[2], match[3]
        notes = notes_by_section[difficulty+suffix]
        phrases, warnings = _phrases(notes, schedules[suffix], score['ppq'])
        events = [line.strip() for line in body.splitlines() if line.strip() and not re.search(r'=\s*S\s+2\s',line)]
        events += [f"{p['start_tick']} = S 2 {p['length']}" for p in phrases]
        events.sort(key=lambda line: int(line.split('=',1)[0].strip()))
        reports.setdefault(INSTRUMENTS[suffix], {})[difficulty] = {'phrase_count': len(phrases), 'phrases': phrases, 'warnings': warnings}
        return f'[{difficulty}{suffix}]\n{{\n' + '\n'.join('  '+line for line in events) + '\n}'
    return SECTION.sub(replace, chart), {'enabled': True,
        'policy': 'Up to two bars roughly every eight active bars; shared Expert windows adapted to retained tier notes; avoid long rests and section crossings.',
        'instruments': reports, 'note': 'Automatic placements follow a musical distribution heuristic, not a universal official formula. Review activation opportunities and sparse fallbacks.'}
