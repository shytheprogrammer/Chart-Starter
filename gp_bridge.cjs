// alphaTab handles GP3/4/5, GPX and GP7/8, repeats, tuplets and playback effects.
const fs = require('fs');
const a = require('./vendor/alphatab/alphaTab.js');
try {
  const score = a.importer.ScoreLoader.loadScoreFromBytes(new Uint8Array(fs.readFileSync(process.argv[2])), new a.Settings());
  const result = {
    title: score.title, artist: score.artist, album: score.album,
    ppq: new a.midi.MidiFile().division,
    tracks: score.tracks.map(t => ({index: t.index, name: t.name, program: t.playbackInfo.program,
      percussion: t.staves.some(s => s.isPercussion), notes: [], techniques: {}})),
    tempos: [], signatures: [], end: 0, tickShift: 0, sections: [], bars: []
  };
  // Capture the playback engine's events rather than approximating written durations.
  const handler = {
    addNote(track, tick, length, pitch, velocity) {
      result.tracks[track].notes.push({tick, pitch, velocity, length});
    },
    addTempo(tick, bpm) {result.tempos.push({tick, bpm});},
    addTimeSignature(tick, numerator, denominator) {result.signatures.push({tick, numerator, denominator});},
    finishTrack(track, tick) {result.end = Math.max(result.end, tick);},
    addTickShift(tick) {result.tickShift = tick;},
    addRest() {}, addControlChange() {}, addProgramChange() {}, addBend() {}, addNoteBend() {}
  };
  const gen = new a.midi.MidiFileGenerator(score, new a.Settings(), handler);
  gen.generate();
  // Carry explicit written ghosts/accents onto the engine's expanded hits.
  // The tick lookup gives each occurrence of a beat, including repeats.
  const pitchEvents = new Map();
  for (const t of result.tracks) for (const n of t.notes) {
    const key = `${t.index}:${n.pitch}`;
    if (!pitchEvents.has(key)) pitchEvents.set(key, []);
    pitchEvents.get(key).push(n);
  }
  for (const events of pitchEvents.values()) events.sort((x, y) => x.tick - y.tick);
  const seen = new Set();
  for (const mb of gen.tickLookup.masterBars) {
    result.bars.push({tick: mb.start, end: mb.end,
      numerator: mb.masterBar.timeSignatureNumerator, denominator: mb.masterBar.timeSignatureDenominator});
    if (mb.masterBar.section) result.sections.push({tick: mb.start, name: mb.masterBar.section.text});
    for (let slice = mb.firstBeat; slice; slice = slice.nextBeat) for (const item of slice.highlightedBeats) {
      const beat = item.beat;
      const start = mb.start + item.playbackStart;
      const key = `${beat.id}:${start}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const track = beat.voice.bar.staff.track;
      if (!beat.voice.bar.staff.isPercussion) {
        for (const note of beat.notes) {
          if (note.isTieDestination) continue;
          const events = pitchEvents.get(`${track.index}:${note.realValue}`) || [];
          let lo = 0, hi = events.length;
          while (lo < hi) {const mid = (lo + hi) >>> 1; if (events[mid].tick < start) lo = mid + 1; else hi = mid;}
          for (let i = lo; i < events.length && events[i].tick < start + beat.playbackDuration; i++) {
            Object.assign(events[i], {hopo: !!note.isHammerPullDestination || !!beat.isLegatoDestination,
              tap: !!note.isLeftHandTapped, fret: note.fret, string: note.string,
              dead: !!note.isDead, palm_mute: !!note.isPalmMute || !!beat.isPalmMute,
              staccato: !!note.isStaccato});
          }
        }
        continue;
      }
      for (const note of beat.notes) {
        const ghost = !!note.isGhost;
        const accent = note.accentuated === a.model.AccentuationType.Normal || note.accentuated === a.model.AccentuationType.Heavy;
        if (!ghost && !accent) continue;
        const articulation = track.percussionArticulations[note.percussionArticulation];
        const pitch = articulation ? articulation.outputMidiNumber : note.percussionArticulation;
        const events = pitchEvents.get(`${track.index}:${pitch}`) || [];
        let lo = 0, hi = events.length;
        while (lo < hi) {const mid = (lo + hi) >>> 1; if (events[mid].tick < start) lo = mid + 1; else hi = mid;}
        for (let i = lo; i < events.length && events[i].tick < start + beat.playbackDuration; i++) {
          events[i].ghost = ghost;
          events[i].accent = accent;
        }
      }
    }
  }
  for (const t of score.tracks) {
    const counts = result.tracks[t.index].techniques;
    for (const staff of t.staves) for (const bar of staff.bars) for (const voice of bar.voices) for (const beat of voice.beats) {
      for (const [key, value] of Object.entries({grace: beat.graceType, tremolo: beat.tremoloSpeed, brush: beat.brushType})) {
        if (value) counts[key] = (counts[key] || 0) + 1;
      }
      for (const note of beat.notes) {
        for (const [key, value] of Object.entries({ghost: note.isGhost, accent: note.accentuated, trill: note.isTrill})) {
          if (value) counts[key] = (counts[key] || 0) + 1;
        }
      }
    }
  }
  process.stdout.write(JSON.stringify(result));
} catch (e) {
  process.stderr.write('Unable to read Guitar Pro file: ' + (e.message || String(e)));
  process.exitCode = 1;
}
