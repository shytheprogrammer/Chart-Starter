"""Read standard/enhanced LRC and map absolute audio times to chart ticks."""
import re
import math

STAMP = r"(\d+):([0-5]\d)(?:[.:](\d{1,3}))?"
LINE = re.compile(r"\[" + STAMP + r"\]")
WORD = re.compile(r"<" + STAMP + r">")

def seconds(match):
    return int(match[1]) * 60 + int(match[2]) + (int(match[3]) / 10 ** len(match[3]) if match[3] else 0)

def parse_lrc(text):
    offset = 0
    for value in re.findall(r"\[offset:([^\]]+)\]", text, re.I):
        try:
            offset = int(value.strip())
        except ValueError:
            raise ValueError('The LRC offset must be a whole number of milliseconds.')
    phrases, boundaries = [], []
    for number, raw in enumerate(text.splitlines(), 1):
        raw = raw.strip().lstrip('\ufeff')
        anchors = list(LINE.finditer(raw))
        if not anchors:
            if raw and not re.fullmatch(r"(?:\[[a-zA-Z][^\]]*\])+", raw):
                raise ValueError(f'LRC line {number}: expected a [minutes:seconds] timestamp.')
            continue
        prefix_end = 0
        for anchor in anchors:
            if raw[prefix_end:anchor.start()].strip():
                raise ValueError(f'LRC line {number}: line timestamps must precede the lyric text.')
            prefix_end = anchor.end()
        content = raw[prefix_end:].strip()
        words = list(WORD.finditer(content))
        if ('<' in content or '>' in content) and not words:
            raise ValueError(f'LRC line {number}: invalid enhanced timestamp.')
        for anchor in anchors:
            start = seconds(anchor)
            boundaries.append(start + offset / 1000)
            tokens, explicit_end = [], None
            if words:
                shift = start - seconds(anchors[0])
                previous = start
                first_token = content[:words[0].start()].strip()
                if first_token:
                    tokens.append((start + offset / 1000, first_token))
                for i, word in enumerate(words):
                    when = seconds(word) + shift
                    token = content[word.end():words[i+1].start() if i+1 < len(words) else len(content)].strip()
                    if '<' in token or '>' in token:
                        raise ValueError(f'LRC line {number}: invalid enhanced timestamp.')
                    previous = when
                    if token:
                        tokens.append((when + offset / 1000, token))
                    elif i == len(words)-1:
                        explicit_end = when + offset / 1000
            elif content:
                tokens = [(start + offset / 1000, content)]
            if tokens:
                phrases.append({'start': start + offset / 1000, 'tokens': tokens,
                                'end': explicit_end, 'enhanced': bool(words),
                                'source_line': number, 'repairs': []})
    if not phrases:
        raise ValueError('The LRC file contains no timed lyrics.')
    phrases.sort(key=lambda p: p['start'])
    for i, phrase in enumerate(phrases):
        if i and phrase['start'] == phrases[i-1]['start']:
            raise ValueError('Two lyric lines share the same timestamp; combine them before exporting.')
        next_start = min((b for b in boundaries if b > phrase['start']), default=None)
        tokens = phrase['tokens']
        # Repair consecutive backward words as one block, retaining text order.
        j = 0
        while j < len(tokens):
            previous = tokens[j-1][0] if j else phrase['start']
            if tokens[j][0] >= previous:
                j += 1
                continue
            stop = j + 1
            while stop < len(tokens) and tokens[stop][0] <= previous:
                stop += 1
            fallback = phrase['end'] if phrase['end'] is not None and phrase['end'] > previous else previous + 3
            right = tokens[stop][0] if stop < len(tokens) else (next_start if next_start is not None and next_start > previous else fallback)
            for k in range(j, stop):
                old, text = tokens[k]
                new = previous + (right - previous) * (k - j + 1) / (stop - j + 1)
                tokens[k] = (new, text)
                phrase['repairs'].append({'kind': 'backward_timestamp', 'source_line': phrase['source_line'],
                                         'text': text, 'original_seconds': old, 'adjusted_seconds': new})
            j = stop
        last = phrase['tokens'][-1][0]
        if next_start is not None and last >= next_start:
            # Keep every word inside its own phrase when its tail overruns the next line.
            first = next(j for j, token in enumerate(tokens) if token[0] >= next_start)
            left = tokens[first-1][0] if first else phrase['start']
            for j in range(first, len(tokens)):
                old, text = tokens[j]
                new = left + (next_start - left) * (j - first + 1) / (len(tokens) - first + 1)
                tokens[j] = (new, text)
                phrase['repairs'].append({'kind': 'phrase_overrun_word', 'source_line': phrase['source_line'],
                                         'text': text, 'original_seconds': old, 'adjusted_seconds': new})
            last = tokens[-1][0]
        end = phrase['end']
        if next_start is not None and (end is None or end > next_start) and any(r['kind'] == 'phrase_overrun_word' for r in phrase['repairs']):
            phrase['repairs'].append({'kind': 'phrase_end_shortened', 'source_line': phrase['source_line'],
                                     'original_seconds': end, 'adjusted_seconds': next_start})
        elif next_start is not None and end is not None and end > next_start:
            phrase['repairs'].append({'kind': 'phrase_end_shortened', 'source_line': phrase['source_line'],
                                     'original_seconds': end, 'adjusted_seconds': next_start})
        if end is not None and end <= last:
            raise ValueError('An enhanced end timestamp must follow the last lyric.')
        phrase['end'] = min(end, next_start) if end is not None and next_start is not None else (end if end is not None else (next_start if next_start is not None else last + 3))
    return phrases, offset

def read_lrc(path):
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Choose an existing LRC file smaller than 2 MB.')
    data = path.read_bytes()
    try:
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        raise ValueError('Save the LRC file as UTF-8 or UTF-16 text.')
    return parse_lrc(text)

def chart_lyrics(score, parsed, audio_delay_ms=0, adjustment_ms=0):
    if not math.isfinite(adjustment_ms) or abs(adjustment_ms) > 3600000:
        raise ValueError('Lyrics adjustment must be between -3600000 and 3600000 milliseconds.')
    phrases, file_offset = parsed
    tempos = {round(t['tick']): round(t['bpm'] * 1000) / 1000 for t in score['tempos']}
    tempos.setdefault(0, 120)
    segments, elapsed, previous, bpm = [], 0.0, 0, tempos[0]
    for tick in sorted(tempos):
        if tick < 0 or tempos[tick] <= 0:
            raise ValueError('Invalid tempo map for lyrics.')
        elapsed += (tick - previous) * 60 / (score['ppq'] * bpm)
        segments.append((elapsed, tick, tempos[tick]))
        previous, bpm = tick, tempos[tick]
    clipped = 0
    def tick_at(time):
        nonlocal clipped
        time += (adjustment_ms - audio_delay_ms) / 1000
        if time < 0:
            clipped += 1
            time = 0
        segment = segments[0]
        for candidate in segments:
            if candidate[0] > time:
                break
            segment = candidate
        return round(segment[1] + (time - segment[0]) * score['ppq'] * segment[2] / 60)
    events, last_end = [], -1
    for index, phrase in enumerate(phrases):
        start = tick_at(phrase['start'])
        if start < last_end:
            raise ValueError('Lyrics overlap after timing adjustment; correct the LRC timestamps.')
        tokens = [(tick_at(t), text) for t, text in phrase['tokens']]
        end = max(tick_at(phrase['end']), tokens[-1][0] + 1)
        if index + 1 < len(phrases):
            end = min(end, tick_at(phrases[index + 1]['start']))
            tokens = [(min(t, max(start, end - 1)), text) for t, text in tokens]
        events.append((start, 1, 'phrase_start'))
        events.extend((tick, 2, 'lyric ' + text) for tick, text in tokens)
        events.append((end, 0, 'phrase_end'))
        last_end = end
    warnings = []
    repairs = [repair for phrase in phrases for repair in phrase.get('repairs', [])]
    if repairs:
        affected = sorted({r['source_line'] for r in repairs})
        warnings.append(f"Automatically repaired {len(repairs)} lyric timings on LRC lines {', '.join(map(str, affected))}. Review lyrics_adjusted.lrc and the detailed repairs in conversion_report.json.")
    if clipped:
        warnings.append(f'{clipped} lyric timestamps before chart start were clamped to tick 0.')
    warnings.append('Missing phrase end times use the next line timestamp, or 3 seconds after the final lyric. Review phrase endings in game.')
    return sorted(events), {'phrases': len(phrases), 'lyric_events': sum(len(p['tokens']) for p in phrases),
        'format': 'enhanced/mixed' if any(p['enhanced'] for p in phrases) else 'standard',
        'file_offset_ms': file_offset, 'adjustment_ms': adjustment_ms, 'audio_delay_ms': audio_delay_ms,
        'warnings': warnings, 'repairs': repairs, 'end_tick': last_end,
        'audio_end_seconds': max(p['end'] for p in phrases) + adjustment_ms / 1000}

def adjusted_lrc(parsed):
    """A reviewable repaired copy; file offset is already baked into timestamps."""
    def stamp(time):
        millis = max(0, round(time * 1000))
        minutes, remainder = divmod(millis, 60000)
        seconds, fraction = divmod(remainder, 1000)
        return f'{minutes:02}:{seconds:02}.{fraction:03}'
    lines = []
    for phrase in parsed[0]:
        text = ''.join(f'<{stamp(t)}>{word} ' for t, word in phrase['tokens'])
        lines.append(f"[{stamp(phrase['start'])}]" + text + f"<{stamp(phrase['end'])}>")
    return '\n'.join(lines) + '\n'
