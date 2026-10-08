"""The searchable in-app guide and the exported user manual share one source."""
TOPICS = {
    'Quick start': '''Chart Starter 1.0 turns a local Guitar Pro score into a Clone Hero song folder.

1. Open the Chart tab and click Load .gp file. Choose a GP, GPX, GP3, GP4 or GP5 score. Modern GP7/GP8 files are supported too. Reading may take a moment.
2. Enter the song BPM when prompted. You can change this field before export. The export contains one BPM marker at tick 0 using this value, plus one 4/4 time-signature marker at tick 0. It also controls the drum Double Bass eligibility rule.
3. In each instrument tab, choose the source track and check Include for the parts you want. Drums are enabled when the file contains a percussion track. Pitched parts are not enabled automatically: confirm the track suggestion and check Include.
4. Review the drum mapping and preview the Expert Guitar/Bass/Rhythm patterns.
5. Supply title/artist, optional recording and lyrics, and an output folder. Fill optional song properties and choose any media/extras.
6. Click Song difficulty calculator if you want a preview. Leave ratings blank to use automatic estimates. Star Power is enabled by default.
7. Click Export Selected Instruments. Open the exported folder, add it to your Clone Hero song library, and scan songs in Clone Hero.
8. Open the created chart in Moonscraper and align everything with the matching recording. Review synchronization, instrument patterns, reductions, lyrics and Star Power before playing or sharing. Read conversion_report.json for assumptions and repairs.

Everything works offline after extracting the Windows release. No Songsterr search or download is included. Keep the executable with its _internal folder; Start.cmd launches it.''',
    'Load files and choose instruments': '''The app imports one GP score at a time. Every enabled instrument must use a track from that score; all parts share its playback note positions, including repeats and tuplets. GP tempo changes are replaced by one starting BPM marker using the entered Song BPM. Every export has one 4/4 time-signature marker at tick 0; all GP time-signature changes are omitted.

The Drums selector lists percussion tracks. Guitar, Bass and Rhythm selectors list playable pitched tracks. Suggestions use track names and MIDI programs; they may need correction. A guitar track can be assigned to a different role deliberately, but enabling several roles from the same track creates several playable versions of the same music.

You can export drums only, one pitched part, or any combination. For guitar-only scores, drums are disabled automatically. At least one instrument must be enabled.

Loading another file refreshes track choices and resets pitched Include switches. Some options such as audio, lyrics, covers, extras and overrides remain selected. Check them carefully when switching songs; remove files or clear paths that no longer match.

The demo.gp and demo-fretted.gp files are original example scores included for practice.

To find a Guitar Pro file, search for the song or artist at https://www.songsterr.com/. Open the desired song and copy its page URL. Visit https://www.songsterr-downloader.com/, paste the Songsterr URL and download the available Guitar Pro file. Then use Load GP in Chart Starter to open the saved file. These are external websites used in your browser; the app does not search or download files itself.''',
    'Drum mapping and strict export': '''1. Select your drum track.
2. Click a row in the mapping table. The row shows MIDI pitch, source drum name, hit count and assigned Clone Hero lane.
3. Use Map selected drum to to change its lane. Yellow/blue/green cymbals and toms share a color but have different Pro Drum flags.
4. Assign every auxiliary instrument yourself. Pedal hi-hat, cowbell, tambourine and similar sounds do not always have a safe default.
5. Choose Ignore only when you intentionally want to omit that source sound.

Strict export blocks unmapped hits, simultaneous same-lane collisions, and timing that needs tick rounding. A collision occurs when two independent hits map to the same controller lane at the same instant. Try another mapping first. Disabling Strict accepts an approximation and records what was lost in the report.

Written ghost/accent annotations are retained when matched to playback. Estimate ghosts / accents from velocity adds estimates for unmarked notes: velocity below 50 becomes a ghost, and 115 or greater becomes an accent. Leave this off unless you want the estimate.

Pro Drums cannot represent every acoustic distinction: hi-hat openness, bell/edge/choke details, every auxiliary drum, and continuous velocities may be reduced. Review flams, grace notes and rolls against the recording.''',
    'Double Bass and drum difficulties': '''Enter a positive song BPM. If it is above 110 BPM, consecutive kick runs with gaps of a sixteenth note or less alternate normal Kick and Double Bass, starting with a normal kick. Runs require at least two kicks; a longer gap resets the alternation. At 110 BPM or slower no Double Bass tags are added by this rule.

This is the eligibility behavior configured for this app. The entered BPM sets the single starting tempo for all exported parts. Changing it changes playback speed; source note ticks stay in place.

Every enabled drum part gets Expert, Hard, Medium and Easy. Expert follows the imported mapped playback hits, subject to documented representational limits. Hard reduces ghost detail, dense kicks and demanding fill coordination. Medium simplifies timekeeping and reduces simultaneous limbs. Easy uses stable simplified hand/kick sections and less coordination. Lower tiers remove hits rather than inventing or shifting their onset times, and remove optional Double Bass.

Read the difficulty counts and reduction warnings in conversion_report.json. Sparse parts can have equal note counts across tiers. Automated reductions should be played and reviewed; they cannot replace a human assessment of the groove.''',
    'Guitar, Bass and Rhythm patterns': '''Check Include and select the track in the instrument tab, then click Preview Expert pattern.

The preview shows playback tick, source pitches and controller colors: G = green, R = red, Y = yellow, B = blue, O = orange. It shows the first 500 positions; the report contains the full Expert mapping.

Five-fret conversion is a musical reduction rather than a literal pitch-to-button assignment. Ordered pitch ranks preserve note repetition, trills and melodic direction within a window. Rests, sections, chords and more than five distinct pitches can reset the window. Long ascending/descending runs are balanced across several windows so the extra pitches do not become an isolated tail. Matching repeated bars and consecutive riffs use consistent fret windows so repeated music keeps the same pattern. Review these transitions against the music.

Octave doublings collapse, and Expert chords use at most three frets with comfortable spans. Matching chord/root shapes use consistent templates; power chords can use skipped-fret dyads. Chords share a sustain length. Sustains get a sixteenth-note release gap before the next attack; muted/staccato notes and very short holds do not get long sustains. Written hammer/pull/legato and left-hand-tap flags guide note types. Not every bend, harmonic, finger or string distinction can fit five frets.

Hard reduces density and caps chords at two frets. Medium uses G/R/Y/B with further reductions; Easy uses G/R/Y and single notes. Retained attacks stay at source onset times.

Bass can optionally use open notes for written open-string single notes on Expert/Hard. It does not infer opens from the lowest pitch. Open notes are removed below Hard.

Use an instrument intensity override if its automatic estimate does not reflect the actual playing demand. The override changes the rating, not its fret patterns.''',
    'Audio, stems and synchronization': '''The main Audio path is optional. Choose your matching OGG, OPUS, MP3 or WAV recording. With no main audio the app includes a silent practice placeholder, not an audible GP rendering.

Use the exact recording/version represented by the GP score. Different intros, live takes, edits, repeats or tempo maps may not align. A constant delay corrects a constant offset; it cannot correct ongoing tempo drift. Fix the source score/recording when timing drifts throughout the song.

Audio delay is whole milliseconds: positive values make the chart start later relative to the recording; negative values make it start sooner. Example: if the chart appears 200 ms too early, try +200. Export again and test. The app uses one BPM marker at the start, set to the entered Song BPM. Align the chart in Moonscraper and add tempo changes there if the recording requires them.

Optional stems are added through the extras picker: Guitar, Bass, Rhythm, combined Drums or numbered drum stems, vocals, keys and crowd. Use synchronized stems and a backing-only main track. Combining a full mix with its separated stems doubles those sounds. The app does not separate, mix, normalize or transcode audio. Choose either combined or numbered drums, not both.

Preview audio is a separate song-list snippet. If supplied, it replaces the normal preview from the main recording. Otherwise Preview start (ms) sets the ordinary snippet start.

Files are copied to standard names in the exported folder; originals stay unchanged.''',
    'Song properties and cover art': '''Title and artist appear in the export panel. General song properties include album, genre, year, charter, icon name, loading text, album track number, playlist position, preview start, optional song length, video start/end and the Modchart flag.

Blank optional fields are omitted. Track/order/timing values are whole numbers. Loading text is a single line; Clone Hero rich text such as <br> can be used when appropriate. Leave song length blank so Clone Hero obtains it from the recording.

Choose Album cover to attach a PNG/JPG/JPEG image. It is copied as album.png or album.jpg. Clear the cover path to omit it. Artwork must be a valid image; Chart Starter does not redraw or resize supplied artwork.

The icon text identifies a Clone Hero song icon, not the album cover. If you attach Song icon image as an extra, its filename supplies the icon name automatically. That custom icon still needs installation into the game's Custom folder.

Mark Modchart only if the chart actually is a modchart. Ordinary automatic conversion does not need that flag.

Video timing and song difficulty have their own Help topics. Metadata does not create tracks, change note timing, or repair an incorrect source score.''',
    'Song difficulty calculator and overrides': '''Click Song difficulty calculator after enabling the parts you want to export. It averages the selected Expert intensity ratings, counting Drums/Pro Drums once and Guitar, Bass and Rhythm individually.

The decimal average is displayed. The exported overall rating is rounded half up to the 0–6 scale (for example 3.50 becomes 4). It is written as diff_band. Unselected parts are excluded; a single enabled part uses its own rating.

Each instrument tab has an optional 0–6 override. Its selected override participates in the song average. The Song override in General properties changes only the overall rating, leaving individual ratings intact. Blank overrides use the automatic value. A rating is metadata; it does not change Easy/Medium/Hard/Expert notes.

Drum estimates consider average/sustained hit density, short bursts, kick speed and three-limb coordination, excluding cymbal/dynamic marker events from hit counts. Pitched-part estimates use note-position density. They are heuristics, not a universal official difficulty formula. Review demands such as technique, endurance and complex patterns that a number alone can miss.

Export recalculates from the current selection and mapping. The report records estimated and selected instrument values, exact averages, chosen overall rating and overrides. After changing the selection, rerun the calculator or export to refresh the displayed number.''',
    'Standard and enhanced LRC lyrics': '''You can find lyric files at https://www.lyricsify.com/. Search for the song and artist, save an available .lrc file, then select it using the Lyrics file picker. Confirm that it matches your exact recording and check whether it has line or word timestamps.

1. Choose a .lrc file in Lyrics (optional), or clear the path to omit lyrics.
2. Use UTF-8 or UTF-16 text. The supplied timings should match the same recording as the GP/audio.
3. Standard LRC gives one timestamp per lyric line, for example [00:12.50]Hello world. That line stays one timed lyric event; the app does not invent individual word timings.
4. Enhanced LRC adds absolute word times, for example [00:12.50]Hello <00:12.90>world, or [00:12.50]<00:12.50>Hello <00:12.90>world. The line timestamp can supply the first word's time.
5. An empty final enhanced marker supplies a phrase end: <00:14.00>. An empty timestamped line also closes the preceding phrase.

Minute:second timestamps allow 1–3 fractional digits. Repeated line timestamps and mixed standard/enhanced files are supported. Untimed metadata is ignored; [offset:100] adds 100 ms to the file's timestamps.

Lyrics adjustment affects only lyrics: positive milliseconds make them later. It also works with the audio-delay compensation and the single entered song BPM. Negative resulting chart times are clamped and reported.

When a phrase lacks an explicit end, the next timestamped line supplies it; the final phrase ends 3 seconds after its final lyric. Review these estimated ends. Lyrics are displayed text, not pitched/scored vocal notes, and apply across all difficulties.''',
    'Automatic lyric repairs and later edits': '''Backward word timestamps are repaired while preserving text order. A consecutive backward block is spaced evenly between its preceding valid word and next valid word. At the end of a line, the next line or an explicit phrase end supplies the right boundary; otherwise a 3-second interval is used.

If a line's words extend past the next line, the overrunning tail is fitted into the remaining interval before the next line. The previous phrase is shortened so the next line starts on time. All words are retained.

The completion notice identifies affected source lines. The report lists original and adjusted seconds and the repair type. The original file is copied as lyrics.lrc and remains unchanged. A repaired copy, lyrics_adjusted.lrc, is included when changes were required.

To refine a repair: open lyrics_adjusted.lrc in your text/LRC editor, adjust against the recording, save it, and select it as the Lyrics input for a new export. Its timestamps already include the original LRC file offset, but not the separate UI lyrics adjustment or audio delay. Do not add the old file offset again. Keep any appropriate UI adjustment for the recording.

Malformed timestamps, invalid encodings and duplicate line starts still require correction. Repairs are practical guesses, so listen and review the affected words.''',
    'Star Power placement': '''Add Star Power is on by default. Every selected instrument and playable difficulty gets earnable reward phrases, using the GP bar grid and original onset times.

The helper places phrases up to two musical bars long, roughly every eight active bars on the exported 4/4 grid. Expert windows guide lower-tier placements, adjusted to the notes that remain. It avoids empty phrases, long rests, section crossings and overlaps. Very short or sparse tiers get short fallback phrases with a report note.

This adds Star Power reward phrases (S 2) without changing the playable notes. It does not add forced drum activation fills, auto-activate Star Power, or replace a drum hit. Use the normal activation method for your controller in Clone Hero.

The report lists start/end ticks, length, note count and review notes for every phrase, instrument and difficulty. Distribution is a musical heuristic, not a universal official placement formula. Playtest reward density and useful activation opportunities, especially around solos, sparse passages and major sections.

Turn Add Star Power off before export if you prefer to add phrases yourself in a chart editor.''',
    'Video and photo backgrounds': '''In the extras panel, choose Photo background or Video background, then Choose file. You can attach both; Clone Hero's display settings determine which is used. Enable song backgrounds/videos in game and test after scanning the song.

Images accept PNG/JPG/JPEG and are copied as background.png or background.jpg. Videos accept MP4, AVI, WebM, OGV and MPEG and are copied as video plus the extension. The filename properties are supplied in song.ini.

Videos are copied as provided, not transcoded. VP8-encoded WebM is the portable choice. Windows MP4 should use H.264; different containers/codecs and platforms can fail to decode. If you get a black video, test or convert its codec externally and re-export.

Video start/end are milliseconds relative to the video: positive start skips forward in it, negative start delays it, and end -1 means no explicit endpoint. Audio delay and lyrics adjustment are separate controls. Loop the song video repeats the background if enabled.

Choose the same extra type again to replace its pending file. Select its row and Remove selected extra to omit it. Originals are preserved; photos and videos are not resized or edited.''',
    'Other extras and custom installation': '''The extras picker also accepts preview audio, instrument stems, crowd audio, highway images, highway videos, highway video config, song icons and color-profile .ini files.

Song assets such as backgrounds, preview and stems go directly into the exported song folder. Player customizations are placed under Extras/Custom, with Extras/INSTALL.txt explaining installation. They do not automatically become the selected player highway/colors when you load this song.

1. Open the exported Extras folder and read INSTALL.txt.
2. Locate Clone Hero's Custom folder: commonly Documents/Clone Hero/Custom on Windows, or PlayerData/Custom in a portable installation.
3. Copy the bundled Custom subfolders into it, checking any existing same-name files before replacing them.
4. Restart Clone Hero or scan Custom Content, then select the highway or color profile in game.
5. A song icon is referenced by its filename without the extension; the export sets that name for an attached icon.

Highway images/videos should be 512x1024. Animated highways require VP8 WebM and are packaged in their own folder with highway.webm. Optional config.ini must accompany that video. Icons should be square and about 64–128 pixels. Color profiles should be valid Clone Hero .ini files. Supplied custom files are copied, not redesigned or validated as complete game configurations.

Each extra type holds one pending file. Choosing another file of that type replaces it. Remove selected extra clears it from the export.''',
    'Export, scan and review': '''Choose an Output folder, then Export Selected Instruments. Each export makes a new artist/title song folder. If that name already exists, a numbered sibling is created rather than overwriting it.

The folder contains notes.chart, song.ini, audio or a silent placeholder, and conversion_report.json. Optional lyrics, artwork, backgrounds, stems and custom extras are included when selected. All enabled parts share the same tempo map and global lyric timeline.

Open exported folder helps you locate the result. Put the entire song folder in a location Clone Hero scans, or add its parent to your song-folder settings. Scan songs in Clone Hero. Custom player assets need the separate installation described in Extras/INSTALL.txt.

Read the report before distributing a chart. Check drum collisions/ignored hits, source and exported counts, all lower-tier reductions, fret windows and chord shapes, repaired lyrics, Star Power placements, instrument and overall ratings, and copied-media warnings.

Playtest with the matching audio. Verify intros/repeats/outros, synchronization across tempo changes, sustain releases, difficult controller transitions, simplified grooves and sparse phrases. Make final charting decisions in your preferred chart editor if needed.''',
    'Troubleshooting': '''No tracks / unreadable file: choose a valid local GP score, below the importer size limit of 64 MB. Encrypted/corrupt/unsupported files may need resaving in Guitar Pro. The bundled Windows release includes its GP reader; keep _internal with ChartStarter.exe.

No percussion track: disable drums and use pitched tabs, or choose a different score. No pitched choices: the score may only contain percussion or empty tracks.

Strict export blocks: map missing pitches, resolve same-lane collisions, or deliberately choose Ignore. Turn Strict off only when you accept the approximation documented in the report.

Bad timing / drift: select the exact recording, check GP repeats and tempo map, and use Audio delay only for a constant offset. The Song BPM field sets the single export tempo. Add any needed tempo changes in Moonscraper.

Lyrics fail: use UTF-8/UTF-16, correct malformed timestamps or duplicate line starts, and review any repaired copy. A file larger than 2 MB is rejected. Negative-time clamping is reported.

Video black or missing: enable song video display and use a supported codec; changing a file extension does not convert its video encoding. Custom highway not listed: install Extras/Custom, restart/scan custom content, and select it in game.

Audio doubled: remove full-mix audio when using its stems; use a backing-only main track. No music: the app produced the intended silent placeholder; add a recording.

Unexpected rating: confirm which parts are enabled, check per-part overrides, rerun the calculator, or apply an overall override. Ratings do not change note patterns.

Permission/path error: choose a writable output folder and existing input files. A fresh named export preserves earlier results. If the executable will not launch, extract the complete ZIP to a new folder and run Start.cmd.''',
    'About Chart Starter': '''Chart Starter
Release 1.0

An offline starting point for converting Guitar Pro playback into Clone Hero drum and five-fret charts. Includes local track selection, drum mapping, four difficulties, five-fret pattern reduction, lyric timing/repairs, Star Power, metadata, song difficulty, media and custom-extra packaging.

Automatic reductions, difficulty estimates, repairs and Star Power placement remain charting aids. Final synchronization and playing quality need review against the source music.

The GP reader uses alphaTab and the included Node.js runtime. The Windows build bundles Python and the required runtime files. Included licenses are provided with the release. No Python installation is needed to use the packaged Windows app.

The app logo is included in assets/chart-starter-logo.png. Help is also provided as HELP.md in the release folder.''',
}

def manual_markdown():
    return '# Chart Starter 1.0 — User Guide\n\n' + '\n\n'.join('## '+title+'\n\n'+body for title,body in TOPICS.items()) + '\n'
