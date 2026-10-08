"""Deterministic, groove-aware Pro Drums reductions inspired by RBN guidance.

No notes are shifted or invented. Each tier is a subset of the preceding tier.
Listening/playtesting is still needed for unusual grooves and fill interpretation.
"""
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class DrumHit:
    tick: int
    lane: int
    cymbal: bool = False
    ghost: bool = False
    accent: bool = False


class Rhythm:
    def __init__(self, score, fallback_bpm, last_tick):
        self.ppq = score['ppq']
        self.tempos = {round(t['tick']): t['bpm'] for t in score['tempos']}
        self.tempos.setdefault(0, fallback_bpm)
        self.tempo_ticks = sorted(self.tempos)
        self.bars = sorted(score.get('bars', []), key=lambda b: b['tick'])
        if not self.bars:
            signatures = {round(s['tick']): s for s in score['signatures']}
            signatures.setdefault(0, {'numerator': 4, 'denominator': 4})
            starts = sorted(signatures)
            end = max(last_tick + 1, score.get('end', 0))
            for i, start in enumerate(starts):
                limit = starts[i + 1] if i + 1 < len(starts) else end
                sig = signatures[start]
                length = self.ppq * 4 * sig['numerator'] / sig['denominator']
                while start < limit:
                    stop = min(start + length, limit)
                    self.bars.append({**sig, 'tick': start, 'end': stop})
                    start = stop
        self.bar_ticks = [b['tick'] for b in self.bars]

    def bpm(self, tick):
        return self.tempos[self.tempo_ticks[max(0, bisect_right(self.tempo_ticks, tick) - 1)]]

    def bar_index(self, tick):
        return max(0, bisect_right(self.bar_ticks, tick) - 1)

    def bar(self, tick):
        return self.bars[self.bar_index(tick)]

    def pulse(self, tick):
        bar = self.bar(tick)
        return self.ppq * 1.5 if bar['denominator'] == 8 and bar['numerator'] % 3 == 0 else self.ppq

    def aligned(self, tick, step):
        phase = (tick - self.bar(tick)['tick']) / step
        return abs(phase - round(phase)) < 1e-6


def _events(hits):
    result = defaultdict(list)
    for hit in hits:
        result[hit.tick].append(hit)
    return dict(result)


def _priority(tick, hits, rhythm, step):
    # Strong grid anchors first, then the backbeat and important crash/accents.
    return (abs(tick - rhythm.bar(tick)['tick']) < 1e-6, rhythm.aligned(tick, step),
            any(h.lane == 1 for h in hits), any(h.accent for h in hits),
            any(h.cymbal and h.lane == 4 for h in hits), len(hits), -tick)


def _thin(hits, rhythm, step_at):
    """Choose an actual source event per musical slot; protect strong beats.

    A spacing pass resolves off-grid neighbors across slots and bar boundaries.
    It may replace a weaker offbeat with the following stronger beat, never snap.
    """
    events = _events(hits)
    slots = {}
    for tick, group in sorted(events.items()):
        step = step_at(tick)
        bar = rhythm.bar(tick)
        key = (rhythm.bar_index(tick), step, math.floor((tick - bar['tick']) / step + 1e-8))
        previous = slots.get(key)
        if previous is None or _priority(tick, group, rhythm, step) > _priority(previous, events[previous], rhythm, step_at(previous)):
            slots[key] = tick
    selected = []
    for tick in sorted(slots.values()):
        reject = False
        while selected and tick - selected[-1] < min(step_at(tick), step_at(selected[-1])) - 1e-6:
            prev = selected[-1]
            if _priority(tick, events[tick], rhythm, step_at(tick)) > _priority(prev, events[prev], rhythm, step_at(prev)):
                selected.pop()
            else:
                reject = True
                break
        if not reject:
            selected.append(tick)
    return [hit for tick in selected for hit in events[tick]]


def _rolls(hits, rhythm, max_gap=None, min_hits=3):
    # Dense snare/tom sequences are potential fills; no audio inference is made.
    ticks = sorted({h.tick for h in hits if h.lane and not h.cymbal})
    rolls, run = [], []
    for tick in ticks:
        if run and tick - run[-1] > (rhythm.ppq / 4 if max_gap is None else max_gap) + 1e-6:
            if len(run) >= min_hits:
                rolls.append((run[0], run[-1]))
            run = []
        run.append(tick)
    if len(run) >= min_hits:
        rolls.append((run[0], run[-1]))
    return rolls


def _hand_limit(hits, limit=2):
    # Preserve the snare and recognizable timekeeper before auxiliary pads.
    chosen = []
    for tick, group in sorted(_events(hits).items()):
        hands = sorted((h for h in group if h.lane),
                       key=lambda h: (h.lane == 1, h.accent, h.cymbal, h.lane == 4, -h.lane), reverse=True)
        chosen.extend(h for h in group if h.lane == 0)
        chosen.extend(hands[:limit])
    return sorted(chosen, key=lambda h: (h.tick, h.lane))


def _triplet_bars(hits, rhythm):
    # In simple meter, reduce a triplet passage to the main pulse rather than
    # blindly deleting alternate triplets and producing an irregular pattern.
    counts = Counter()
    for tick in _events(hits):
        bar = rhythm.bar(tick)
        if bar['denominator'] == 8 and bar['numerator'] % 3 == 0:
            continue
        phase = (tick - bar['tick']) % rhythm.ppq
        if any(abs(phase - rhythm.ppq * f) < 1 for f in (1/3, 2/3)):
            counts[rhythm.bar_index(tick)] += 1
    return {bar for bar, count in counts.items() if count >= 2}


def _single_kick_per_fast_bar(hits, rhythm):
    kicks = defaultdict(list)
    other = [h for h in hits if h.lane]
    for hit in hits:
        if not hit.lane:
            kicks[rhythm.bar_index(hit.tick)].append(hit)
    crash_ticks = {h.tick for h in other if h.cymbal and h.lane == 4}
    for group in kicks.values():
        if any(rhythm.bpm(h.tick) >= 170 for h in group):
            group = [max(group, key=lambda h: (rhythm.aligned(h.tick, rhythm.pulse(h.tick)), h.tick in crash_ticks, -h.tick))]
        other.extend(group)
    return sorted(other, key=lambda h: (h.tick, h.lane))


def _hard(hits, rhythm):
    hits = [h for h in hits if not h.ghost]
    rolls = _rolls(hits, rhythm)
    short = [(start, end) for start, end in rolls if end - start <= 2 * rhythm.ppq and
             all(rhythm.bpm(h.tick) < 140 for h in hits if start <= h.tick <= end)]

    def hand_step(tick):
        if any(start <= tick <= end for start, end in short):
            return rhythm.ppq / 4
        return rhythm.pulse(tick) if rhythm.bpm(tick) >= 170 else rhythm.ppq / 2

    cymbals = _thin([h for h in hits if h.cymbal], rhythm,
                    lambda t: rhythm.pulse(t) if rhythm.bpm(t) >= 170 else rhythm.ppq / 2)
    pads = _thin([h for h in hits if h.lane and not h.cymbal], rhythm, hand_step)
    kicks = _thin([h for h in hits if not h.lane and not any(a <= h.tick <= b for a, b in rolls)],
                  rhythm, lambda t: rhythm.pulse(t) if rhythm.bpm(t) >= 170 else rhythm.ppq / 2)
    return _hand_limit(cymbals + pads + kicks)


def _medium(hits, rhythm, triplets):

    def hand_step(tick):
        if rhythm.bpm(tick) >= 140 or rhythm.bar_index(tick) in triplets:
            return rhythm.pulse(tick)
        return rhythm.ppq / 2

    hands = _thin([h for h in hits if h.lane], rhythm, hand_step)
    # If right-hand timekeeping exists in a measure, don't place isolated
    # snare/kick hits between those cymbal hits on Medium.
    # If density reduction removes offbeat timekeeping entirely, retain the
    # kick/snare pulse instead of mistakenly deleting that whole groove too.
    clock_bars = {rhythm.bar_index(h.tick) for h in hands if h.cymbal and h.lane in (2, 3)}
    clock_ticks = {h.tick for h in hands if h.cymbal}
    fills = _rolls([h for h in hits if h.lane and not h.cymbal and h.tick not in clock_ticks],
                   rhythm, max_gap=rhythm.ppq / 2, min_hits=2)
    hands = [h for h in hands if h.cymbal or rhythm.bar_index(h.tick) not in clock_bars or
             h.tick in clock_ticks or any(a <= h.tick <= b for a, b in fills)]
    kicks = [h for h in hits if not h.lane and
             (rhythm.bpm(h.tick) <= 110 or rhythm.aligned(h.tick, rhythm.pulse(h.tick))) and
             (rhythm.bar_index(h.tick) not in clock_bars or h.tick in clock_ticks)]
    kicks = _thin(kicks, rhythm, lambda t: rhythm.ppq / 2 if rhythm.bpm(t) <= 110 else rhythm.pulse(t))
    combined = []
    for tick, group in sorted(_events(hands + kicks).items()):
        if len(group) > 2:
            crash = next((h for h in group if h.cymbal and h.lane == 4), None)
            kick = next((h for h in group if not h.lane), None)
            if crash and kick and rhythm.aligned(tick, rhythm.pulse(tick)):
                group = [crash, kick]
            else:
                # Preserve two-hand snare/timekeeping instead of adding a third limb.
                group = sorted(group, key=lambda h: (h.lane == 1, h.cymbal, h.accent), reverse=True)[:2]
        combined.extend(replace(h, ghost=False, accent=False) for h in group)
    combined = _single_kick_per_fast_bar(combined, rhythm)
    result, last_crash = [], None
    for tick, group in sorted(_events(combined).items()):
        if last_crash is not None and rhythm.bpm(tick) >= 140 and tick - last_crash < rhythm.pulse(tick) - 1e-6:
            continue
        result.extend(group)
        if any(h.cymbal and h.lane == 4 for h in group):
            last_crash = tick
    return result


def _easy(hits, rhythm, score):
    # Use actual practice sections when supplied; otherwise stable 8-bar blocks.
    section_starts = sorted({round(s['tick']) for s in score.get('sections', [])} | {0})
    use_sections = len(section_starts) > 1

    def section_key(tick):
        return (max(0, bisect_right(section_starts, tick) - 1) if use_sections
                else rhythm.bar_index(tick) // 8)

    sections = defaultdict(list)
    for hit in hits:
        sections[section_key(hit.tick)].append(hit)
    # Introduce the pedal in at most two quieter sections; other sections use hands.
    candidates = [key for key, group in sections.items() if any(h.lane == 0 for h in group) and
                  any(h.lane == 1 for h in group)]
    candidates.sort(key=lambda key: (sum(h.lane > 1 for h in sections[key]) / len(sections[key]), key))
    kick_sections = set(candidates[:min(2, max(1, len(sections) // 3))])
    eligible, modes = [], []
    for key, group in sorted(sections.items()):
        mode = 'kick_snare' if key in kick_sections or not any(h.lane for h in group) else 'hands'
        modes.append({'start_tick': min(h.tick for h in group), 'end_tick': max(h.tick for h in group), 'mode': mode})
        if mode == 'hands':
            group = [h for h in group if h.lane]
        else:
            crash_ticks = {h.tick for h in group if h.cymbal and h.lane == 4}
            group = [h for h in group if h.lane in (0, 1) or (h.cymbal and h.lane == 4)]
            # Crash accents replace the kick in a pedal/snare section.
            group = [h for h in group if h.lane != 0 or h.tick not in crash_ticks]
        eligible.extend(group)
    result = _thin(eligible, rhythm, rhythm.pulse)
    result = _hand_limit(result)
    # Defensive rule: Easy never pairs a kick with any cymbal.
    cymbal_ticks = {h.tick for h in result if h.cymbal}
    result = [h for h in result if h.lane != 0 or h.tick not in cymbal_ticks]
    return _single_kick_per_fast_bar(result, rhythm), modes


def _gems(hits):
    gems = []
    for h in hits:
        gems.append((h.tick, h.lane))
        if h.cymbal:
            gems.append((h.tick, 64 + h.lane))
        if h.accent and h.lane:
            gems.append((h.tick, 33 + h.lane))
    return sorted(gems)


def downchart(score, expert_gems, song_bpm):
    flags = set(expert_gems)
    hits = [DrumHit(tick, lane, (tick, 64 + lane) in flags,
                    (tick, 39 + lane) in flags, (tick, 33 + lane) in flags)
            for tick, lane in expert_gems if 0 <= lane <= 4]
    rhythm = Rhythm(score, song_bpm, max(h.tick for h in hits))
    warnings = []

    def nonempty(reduced, parent, name):
        if reduced:
            return reduced
        # Retain one genuine source hit rather than fabricating a pulse for a
        # very sparse/off-grid/ghost-only part. Explicitly flag it for review.
        warnings.append(f'{name}: source is sparse or atypical; retained one source hit for manual review.')
        return [replace(max(parent, key=lambda h: (h.accent, h.lane == 1, -h.tick)), ghost=False, accent=False)]

    hard = nonempty(_hard(hits, rhythm), hits, 'Hard')
    medium = nonempty(_medium(hard, rhythm, _triplet_bars(hits, rhythm)), hard, 'Medium')
    easy, modes = _easy(medium, rhythm, score)
    easy = nonempty(easy, medium, 'Easy')
    tiers = {'Hard': hard, 'Medium': medium, 'Easy': easy}
    if any(h.lane == 1 for h in hard) and not any(h.lane == 1 for h in medium):
        warnings.append('Medium lost the snare/backbeat during coordination reduction; review this unusual groove.')
    report = {'method': 'Expert → Hard → Medium → Easy; RBN-inspired musical and coordination reductions',
              'automatic': True, 'manual_playtest_recommended': True, 'warnings': warnings,
              'easy_section_modes': modes, 'difficulties': {}}
    report['difficulties']['Expert'] = {'hits': sum(lane <= 4 or lane == 32 for _, lane in expert_gems),
                                        'double_bass_hits': sum(lane == 32 for _, lane in expert_gems)}
    parent_count = report['difficulties']['Expert']['hits']
    for name, tier in tiers.items():
        report['difficulties'][name] = {'hits': len(tier), 'removed_from_previous': parent_count - len(tier),
                                       'kicks': sum(h.lane == 0 for h in tier),
                                       'cymbals': sum(h.cymbal for h in tier),
                                       'max_simultaneous_limbs': max(map(len, _events(tier).values())),
                                       'double_bass_hits': 0}
        parent_count = len(tier)
    # Sparse Expert charts can legitimately have identical lower difficulties.
    if len(hard) == report['difficulties']['Expert']['hits'] or len(hard) == len(medium) or len(medium) == len(easy):
        report['warnings'].append('One or more tiers have equal note counts; review sparse/simple passages rather than forcing arbitrary deletions.')
    return {name: _gems(tier) for name, tier in tiers.items()}, report
