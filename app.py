"""Chart Starter: local GP-to-Clone-Hero chart creation."""
from pathlib import Path
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import webbrowser

from core import (AppError, DEFAULT_MAP, LANES, PITCH_NAMES, export_song, read_gp, convert_song, ROOT)
from properties import TEXT_FIELDS, NUMBER_FIELDS
from fretted import chart_fretted, TRACK_NAMES
from extras import EXTRA_TYPES
from branding import APP_NAME, RELEASE_VERSION
from help_tab import HelpTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME} {RELEASE_VERSION}')
        self.geometry('1060x860')
        self.minsize(900, 750)
        self.configure(bg='#edf1f7')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#edf1f7')
        style.configure('TLabel', background='#edf1f7')
        style.configure('TLabelframe', background='#edf1f7')
        style.configure('TLabelframe.Label', background='#edf1f7', font=('Segoe UI', 11, 'bold'))
        style.configure('TButton', padding=(10, 6))
        style.configure('Accent.TButton', background='#2563eb', foreground='white')
        style.configure('Treeview', rowheight=25)
        self.loaded_file = tk.StringVar(value="No file loaded.")
        self.title_var = tk.StringVar()
        self.artist_var = tk.StringVar()
        self.audio = tk.StringVar()
        self.lyrics = tk.StringVar()
        self.lyrics_offset = tk.StringVar(value='0')
        self.properties = {key: tk.StringVar(value='Chart Starter' if key == 'charter' else '')
                           for key in (*TEXT_FIELDS, *NUMBER_FIELDS)}
        self.modchart = tk.BooleanVar(value=False)
        self.album_art = tk.StringVar()
        self.intensity_override = tk.StringVar()
        self.intensity_info = tk.StringVar(value='Song difficulty averages the selected instrument ratings. Scale: 0–6.')
        self.drum_intensity_override = tk.StringVar()
        self.star_power_enabled = tk.BooleanVar(value=True)
        self.video_loop = tk.BooleanVar(value=False)
        self.extras = {}
        self.extra_role = tk.StringVar(value='Photo background')
        self.drums_enabled = tk.BooleanVar(value=True)
        self.pitched_tracks = []
        self.fretted = {role: {'enabled': tk.BooleanVar(value=False), 'track': tk.StringVar(),
                              'override': tk.StringVar(), 'open': tk.BooleanVar(value=False),
                              'info': tk.StringVar(value='Select a pitched GP track, then preview the five-fret reduction.')}
                        for role in TRACK_NAMES}
        self.output = tk.StringVar(value=str(Path.home() / 'Documents' / 'Chart Starter' / 'Songs'))
        self.offset = tk.StringVar(value='0')
        self.strict = tk.BooleanVar(value=True)
        self.dynamics = tk.BooleanVar(value=False)
        self.song_bpm = tk.StringVar()
        self.status = tk.StringVar(value='Load a Guitar Pro file to begin.')
        self.track_var = tk.StringVar()
        self.map_var = tk.StringVar()
        self.messages = queue.Queue()
        self.busy = False
        self.score = None
        self.tracks = []
        self.mapping = {}
        self.selected_pitch = None
        self.last_export = None
        self.buttons = []
        self.build()
        self.after(100, self.poll)

    def button(self, parent, text, command, accent=False):
        b = ttk.Button(parent, text=text, command=command, style='Accent.TButton' if accent else 'TButton')
        self.buttons.append(b)
        return b

    def build(self):
        header = ttk.Frame(self, padding=(18,10)); header.pack(fill='x')
        self.logo_full = tk.PhotoImage(file=str(ROOT/'assets'/'chart-starter-logo.png'))
        self.logo = self.logo_full.subsample(max(1,(self.logo_full.width()+63)//64))
        self.iconphoto(True, self.logo)
        ttk.Label(header, image=self.logo).pack(side='left', padx=(0,12))
        identity = ttk.Frame(header); identity.pack(side='left')
        ttk.Label(identity, text=APP_NAME, font=('Segoe UI',24,'bold')).pack(anchor='w')
        ttk.Label(identity, text=f'Release {RELEASE_VERSION} • Guitar Pro to Clone Hero', foreground='#526078').pack(anchor='w')
        self.main_tabs = ttk.Notebook(self); self.main_tabs.pack(fill='both',expand=True)
        chart_page = ttk.Frame(self.main_tabs)
        self.main_tabs.add(chart_page, text='Chart')
        self.help = HelpTab(self.main_tabs)
        self.main_tabs.add(self.help, text='Help')
        ttk.Button(header, text='Help', command=lambda:self.main_tabs.select(self.help)).pack(side='right')
        viewport = ttk.Frame(chart_page)
        viewport.pack(fill='both', expand=True)
        canvas = tk.Canvas(viewport, background='#edf1f7', highlightthickness=0)
        scroll = ttk.Scrollbar(viewport, orient='vertical', command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        body = ttk.Frame(canvas, padding=18)
        window = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        self.bind_all('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units')
                      if self.main_tabs.index(self.main_tabs.select()) == 0 and event.widget.winfo_class() not in ('Treeview', 'TCombobox','Text','Listbox') else None)
        ttk.Label(body, text='Build your chart', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(body, text='Load a GP file · choose your instrument tracks · preview the patterns · export a song folder', foreground='#526078').pack(anchor='w', pady=(2, 12))
        source = ttk.LabelFrame(body, text='1   Load your Guitar Pro file', padding=10)
        source.pack(fill='x')
        self.button(source, 'Load .gp file…', self.open_local, True).pack(side='left')
        ttk.Label(source, textvariable=self.loaded_file, wraplength=760).pack(side='left', padx=12)

        instruments = ttk.LabelFrame(body, text='2   Instrument tracks', padding=10)
        instruments.pack(fill='both', expand=True, pady=10)
        self.instrument_tabs = ttk.Notebook(instruments)
        self.instrument_tabs.pack(fill='both', expand=True)
        part = ttk.Frame(self.instrument_tabs, padding=10)
        self.instrument_tabs.add(part, text='Drums')
        ttk.Checkbutton(part, text='Include drums in export', variable=self.drums_enabled).pack(anchor='w')
        drum_rating = ttk.Frame(part); drum_rating.pack(fill='x', pady=4)
        ttk.Label(drum_rating, text='Drum intensity override (blank = auto)').pack(side='left')
        ttk.Combobox(drum_rating, textvariable=self.drum_intensity_override, values=['', '0', '1', '2', '3', '4', '5', '6'], state='readonly', width=5).pack(side='left', padx=8)
        row = ttk.Frame(part)
        row.pack(fill='x')
        ttk.Label(row, text='Drum track').pack(side='left', padx=(0, 8))
        self.track_combo = ttk.Combobox(row, textvariable=self.track_var, state='readonly')
        self.track_combo.pack(side='left', fill='x', expand=True)
        self.track_combo.bind('<<ComboboxSelected>>', self.track_selected)
        self.track_info = ttk.Label(part, text='No file loaded.', foreground='#526078')
        self.track_info.pack(anchor='w', pady=(5, 5))
        mapping_frame = ttk.Frame(part)
        mapping_frame.pack(fill='both', expand=True)
        self.map_tree = ttk.Treeview(mapping_frame, columns=('pitch', 'instrument', 'hits', 'lane'), show='headings', height=6, selectmode='browse')
        for col, label, width in [('pitch', 'MIDI pitch', 80), ('instrument', 'Source drum', 230), ('hits', 'Hits', 70), ('lane', 'Clone Hero lane', 380)]:
            self.map_tree.heading(col, text=label)
            self.map_tree.column(col, width=width)
        self.map_tree.pack(side='left', fill='both', expand=True)
        mapping_scroll = ttk.Scrollbar(mapping_frame, command=self.map_tree.yview)
        mapping_scroll.pack(side='right', fill='y')
        self.map_tree.configure(yscrollcommand=mapping_scroll.set)
        self.map_tree.tag_configure('unmapped', foreground='#b45309')
        self.map_tree.bind('<<TreeviewSelect>>', self.pitch_selected)
        row = ttk.Frame(part)
        row.pack(fill='x', pady=(7, 0))
        ttk.Label(row, text='Map selected drum to').pack(side='left', padx=(0, 8))
        self.map_combo = ttk.Combobox(row, values=list(LANES), textvariable=self.map_var, state='readonly', width=30)
        self.map_combo.pack(side='left')
        self.map_combo.bind('<<ComboboxSelected>>', self.change_mapping)
        ttk.Label(row, text='Pedal hi-hat and auxiliary percussion require your choice.', foreground='#526078').pack(side='left', padx=12)

        for role, settings in self.fretted.items():
            tab = ttk.Frame(self.instrument_tabs, padding=10)
            self.instrument_tabs.add(tab, text=role)
            row = ttk.Frame(tab); row.pack(fill='x')
            ttk.Checkbutton(row, text=f'Include {role.lower()}', variable=settings['enabled']).pack(side='left')
            ttk.Label(row, text='GP track').pack(side='left', padx=10)
            settings['combo'] = ttk.Combobox(row, textvariable=settings['track'], state='readonly', width=50)
            settings['combo'].pack(side='left', fill='x', expand=True)
            row = ttk.Frame(tab); row.pack(fill='x', pady=8)
            self.button(row, 'Preview Expert pattern', lambda role=role: self.preview_fretted(role)).pack(side='left')
            ttk.Label(row, text='Intensity override (blank = auto)').pack(side='left', padx=10)
            ttk.Combobox(row, textvariable=settings['override'], values=['', '0', '1', '2', '3', '4', '5', '6'], state='readonly', width=5).pack(side='left')
            if role == 'Bass':
                ttk.Checkbutton(row, text='Use opens for written open-string single notes', variable=settings['open']).pack(side='left', padx=10)
            ttk.Label(tab, textvariable=settings['info'], wraplength=900).pack(anchor='w')
            ttk.Label(tab, text='Phrase-based pitch order • repeated patterns • comfortable chords • sustain gaps • written HOPO/tap flags', foreground='#526078').pack(anchor='w', pady=4)
            table_frame = ttk.Frame(tab); table_frame.pack(fill='both', expand=True)
            tree = ttk.Treeview(table_frame, columns=('tick', 'pitch', 'lanes'), show='headings', height=6)
            for column, label, width in [('tick', 'Playback tick', 120), ('pitch', 'Source pitches', 250), ('lanes', 'Expert controller pattern', 380)]:
                tree.heading(column, text=label); tree.column(column, width=width)
            tree.pack(side='left', fill='both', expand=True)
            scroll = ttk.Scrollbar(table_frame, command=tree.yview); scroll.pack(side='right', fill='y')
            tree.configure(yscrollcommand=scroll.set); settings['preview'] = tree
            ttk.Label(tab, text='Exports Expert, Hard, Medium and Easy. Review reductions against the recording.', foreground='#526078').pack(anchor='w', pady=4)

        dest = ttk.LabelFrame(body, text='3   Export the song folder', padding=10)
        dest.pack(fill='x')
        dest.columnconfigure(1, weight=1)
        ttk.Label(dest, text='Title / artist').grid(row=0, column=0, sticky='w', padx=(0, 8))
        fields = ttk.Frame(dest)
        fields.grid(row=0, column=1, columnspan=2, sticky='ew')
        ttk.Entry(fields, textvariable=self.title_var).pack(side='left', fill='x', expand=True)
        ttk.Entry(fields, textvariable=self.artist_var).pack(side='left', fill='x', expand=True, padx=(8, 0))
        ttk.Label(dest, text='Audio (optional)').grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(dest, textvariable=self.audio).grid(row=1, column=1, sticky='ew', pady=5)
        self.button(dest, 'Browse…', self.choose_audio).grid(row=1, column=2, padx=(8, 0))
        ttk.Label(dest, text='No audio selected → silent practice track. Add your recording for music.', foreground='#526078').grid(row=2, column=1, columnspan=2, sticky='w')
        ttk.Label(dest, text='Output folder').grid(row=3, column=0, sticky='w', pady=5)
        ttk.Entry(dest, textvariable=self.output).grid(row=3, column=1, sticky='ew', pady=5)
        self.button(dest, 'Browse…', self.choose_output).grid(row=3, column=2, padx=(8, 0))
        row = ttk.Frame(dest)
        row.grid(row=4, column=0, columnspan=3, sticky='ew', pady=(4, 0))
        ttk.Label(row, text='Audio delay (ms)').pack(side='left')
        ttk.Entry(row, textvariable=self.offset, width=9).pack(side='left', padx=8)
        ttk.Checkbutton(row, text='Strict: block unmapped hits / collisions', variable=self.strict).pack(side='left', padx=8)
        ttk.Checkbutton(row, text='Estimate ghosts / accents from velocity', variable=self.dynamics).pack(side='left', padx=8)
        row = ttk.Frame(dest)
        row.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(8, 0))
        ttk.Label(row, text='Song BPM').pack(side='left')
        ttk.Entry(row, textvariable=self.song_bpm, width=8).pack(side='left', padx=8)
        ttk.Label(row, text='Above 110 BPM: alternate Double Bass on consecutive 16th notes or faster.').pack(side='left')
        ttk.Label(dest, text='Exports Expert, Hard, Medium and Easy. Lower difficulties simplify the groove, fills and coordination.',
                  foreground='#526078').grid(row=6, column=0, columnspan=3, sticky='w', pady=(8, 0))
        ttk.Label(dest, text='Lyrics (optional)').grid(row=7, column=0, sticky='w', pady=5)
        ttk.Entry(dest, textvariable=self.lyrics).grid(row=7, column=1, sticky='ew')
        self.button(dest, 'Browse…', self.choose_lyrics).grid(row=7, column=2, padx=(8, 0))
        row = ttk.Frame(dest)
        row.grid(row=8, column=0, columnspan=3, sticky='w')
        ttk.Label(row, text='Lyrics adjustment (ms)').pack(side='left')
        ttk.Entry(row, textvariable=self.lyrics_offset, width=9).pack(side='left', padx=8)
        ttk.Label(row, text='Positive = later. Standard line or enhanced word timestamps; clear the path to omit.').pack(side='left')
        props = ttk.LabelFrame(body, text='4   General song properties', padding=10)
        props.pack(fill='x', pady=(10, 0))
        props.columnconfigure(1, weight=1)
        props.columnconfigure(3, weight=1)
        for index, (key, label) in enumerate({**TEXT_FIELDS, **NUMBER_FIELDS}.items()):
            r, c = divmod(index, 2)
            ttk.Label(props, text=label).grid(row=r, column=c*2, sticky='w', padx=(0, 8), pady=3)
            ttk.Entry(props, textvariable=self.properties[key]).grid(row=r, column=c*2+1, sticky='ew', padx=(0, 12), pady=3)
        ttk.Label(props, text='Blank optional fields are omitted. Leave song length blank for Clone Hero to read the audio.', foreground='#526078').grid(row=6, column=0, columnspan=4, sticky='w', pady=4)
        ttk.Checkbutton(props, text='Modchart', variable=self.modchart).grid(row=7, column=0, sticky='w')
        ttk.Label(props, text='Album cover (optional)').grid(row=8, column=0, sticky='w')
        ttk.Entry(props, textvariable=self.album_art).grid(row=8, column=1, columnspan=2, sticky='ew')
        self.button(props, 'Browse…', self.choose_art).grid(row=8, column=3, sticky='e')
        rating = ttk.Frame(props)
        rating.grid(row=9, column=0, columnspan=4, sticky='ew', pady=8)
        self.button(rating, 'Song difficulty calculator', self.calculate_intensity).pack(side='left')
        ttk.Label(rating, text='Song override (blank = average)').pack(side='left', padx=10)
        ttk.Combobox(rating, textvariable=self.intensity_override, values=['', '0', '1', '2', '3', '4', '5', '6'], state='readonly', width=6).pack(side='left')
        ttk.Label(props, textvariable=self.intensity_info, wraplength=930).grid(row=10, column=0, columnspan=4, sticky='w')
        ttk.Label(props, text='Averages only enabled parts, using their selected ratings. Per-instrument overrides are in their tabs.', foreground='#526078').grid(row=11, column=0, columnspan=4, sticky='w')
        media = ttk.LabelFrame(body, text='5   Star Power, backgrounds and extras', padding=10)
        media.pack(fill='x', pady=(10, 0))
        ttk.Checkbutton(media, text='Add Star Power to every exported instrument and difficulty', variable=self.star_power_enabled).pack(anchor='w')
        ttk.Checkbutton(media, text='Loop the song video', variable=self.video_loop).pack(anchor='w')
        ttk.Label(media, text='Short musical phrases, spaced through active passages. Review the placements in game.', foreground='#526078').pack(anchor='w', pady=4)
        row = ttk.Frame(media); row.pack(fill='x')
        ttk.Combobox(row, textvariable=self.extra_role, values=list(EXTRA_TYPES), state='readonly', width=29).pack(side='left')
        self.button(row, 'Choose file…', self.choose_extra).pack(side='left', padx=8)
        self.button(row, 'Remove selected extra', self.remove_extra).pack(side='left')
        self.extra_tree = ttk.Treeview(media, columns=('type','file'), show='headings', height=4, selectmode='browse')
        self.extra_tree.heading('type', text='Extra'); self.extra_tree.column('type',width=220)
        self.extra_tree.heading('file', text='Selected file'); self.extra_tree.column('file',width=650)
        self.extra_tree.pack(fill='x', pady=6)
        ttk.Label(media, text='Video/photo backgrounds, preview and stems go in the song folder. Highways, icons and colors are packaged with Custom-folder instructions.', wraplength=940, foreground='#526078').pack(anchor='w')
        ttk.Label(media, text='Videos are copied as supplied. VP8 WebM works across platforms; use H.264 for Windows MP4. Video timing uses Video start (ms) above.', wraplength=940, foreground='#526078').pack(anchor='w', pady=4)
        ttk.Label(media, text='For stems, use a backing-only main audio track to avoid doubling the full mix. Clear a file path to omit the album cover.', wraplength=940, foreground='#526078').pack(anchor='w')
        row = ttk.Frame(body)
        row.pack(fill='x', pady=(10, 6))
        self.button(row, 'Export Selected Instruments', self.export, True).pack(side='left')
        self.button(row, 'Open exported folder', self.open_export).pack(side='left', padx=8)
        self.progress = ttk.Progressbar(row, mode='indeterminate', length=160)
        self.progress.pack(side='right')
        ttk.Label(body, textvariable=self.status, wraplength=980, foreground='#34445f').pack(anchor='w')

    def run_job(self, label, work, done):
        if self.busy:
            return
        self.busy = True
        self.status.set(label)
        for b in self.buttons:
            b.state(['disabled'])
        self.track_combo.configure(state='disabled')
        self.map_combo.configure(state='disabled')
        for settings in self.fretted.values(): settings['combo'].configure(state='disabled')
        self.progress.start(15)

        def worker():
            try:
                self.messages.put((done, work(), None))
            except Exception as e:
                self.messages.put((done, None, e))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            done, result, error = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            for b in self.buttons:
                b.state(['!disabled'])
            self.track_combo.configure(state='readonly')
            self.map_combo.configure(state='readonly')
            for settings in self.fretted.values(): settings['combo'].configure(state='readonly')
            if error:
                self.status.set(str(error))
                messagebox.showerror('Action could not be completed', str(error), parent=self)
            else:
                done(result)
        self.after(100, self.poll)

    def open_local(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title='Open Guitar Pro file', filetypes=[('Guitar Pro', '*.gp *.gp7 *.gp8 *.gpx *.gp5 *.gp4 *.gp3'), ('All files', '*.*')])
        if path:
            self.run_job('Reading Guitar Pro tracks…', lambda: (Path(path), read_gp(Path(path))), self.loaded)

    def loaded(self, result):
        path, self.score = result
        self.loaded_file.set(str(path))
        self.song_bpm.set('')
        self.title_var.set(self.score['title'] or path.stem)
        self.artist_var.set(self.score['artist'] or 'Unknown artist')
        for key in ('album', 'genre', 'year'):
            self.properties[key].set(self.score.get(key, '') or '')
        self.intensity_info.set('Song difficulty averages only the selected instrument ratings. Recalculated at export.')
        self.tracks = [t for t in self.score['tracks'] if t['percussion']]
        self.pitched_tracks = [t for t in self.score['tracks'] if not t['percussion'] and t['notes']]
        self.drums_enabled.set(bool(self.tracks))
        for role, settings in self.fretted.items():
            settings['combo'].configure(values=[f"{t['index']+1}. {t['name']} ({len(t['notes'])} notes)" for t in self.pitched_tracks])
            settings['track'].set(''); settings['enabled'].set(False)
            settings['preview'].delete(*settings['preview'].get_children())
            settings['info'].set('Choose a track, enable this part and preview its five-fret pattern.')
            candidates = [i for i,t in enumerate(self.pitched_tracks) if role.lower() in t['name'].lower() or
                          (role == 'Bass' and 32 <= t.get('program', -1) <= 39)]
            if candidates: settings['combo'].current(candidates[0])
            elif self.pitched_tracks: settings['combo'].current(0)
        self.map_tree.delete(*self.map_tree.get_children())
        self.track_var.set('')
        self.mapping = {}
        self.selected_pitch = None
        self.track_combo.configure(values=[f"{t['index'] + 1}. {t['name']} ({len(t['notes'])} hits)" for t in self.tracks])
        if self.tracks:
            self.track_combo.current(0)
            self.track_selected()
            self.status.set(f'Loaded {path.name}. Choose a drum track and review its mapping before exporting.')
            self.ask_song_bpm()
        else:
            self.track_info.configure(text=f'{len(self.score["tracks"])} tracks in this file; none marked as percussion.')
            self.status.set('No drums in this file. Choose Guitar, Bass or Rhythm tracks to export.')
            if self.pitched_tracks: self.ask_song_bpm()

    def ask_song_bpm(self):
        initial = next((t['bpm'] for t in self.score['tempos'] if t['tick'] == 0), 120)
        bpm = simpledialog.askfloat('Song BPM',
            'What is the song BPM? This sets the single starting BPM marker.\nAbove 110 BPM, consecutive 16th-note kicks or faster alternate Double Bass.',
            parent=self, initialvalue=initial, minvalue=0.001)
        if bpm is not None:
            self.song_bpm.set(f'{bpm:g}')
        else:
            self.status.set('Enter the song BPM before exporting.')

    def track_selected(self, _=None):
        if self.busy:
            return
        index = self.track_combo.current()
        if index < 0:
            return
        track = self.tracks[index]
        counts = {}
        for n in track['notes']:
            counts[n['pitch']] = counts.get(n['pitch'], 0) + 1
        self.mapping = {p: DEFAULT_MAP[p] for p in counts if p in DEFAULT_MAP}
        self.selected_pitch = None
        self.map_var.set('')
        self.map_tree.delete(*self.map_tree.get_children())
        for pitch, count in sorted(counts.items()):
            self.map_tree.insert('', 'end', iid=str(pitch), values=(pitch, PITCH_NAMES.get(pitch, 'Auxiliary percussion'), count, self.mapping.get(pitch, 'Choose a lane…')), tags=() if pitch in self.mapping else ('unmapped',))
        self.track_info.configure(text=f"{len(track['notes'])} playback hits · {len(counts)} drum pitches · {self.score['ppq']} ticks per quarter note")

    def pitch_selected(self, _=None):
        if self.busy:
            return
        selected = self.map_tree.selection()
        if selected:
            self.selected_pitch = int(selected[0])
            self.map_var.set(self.mapping.get(self.selected_pitch, ''))

    def change_mapping(self, _=None):
        if self.busy or self.selected_pitch is None:
            return
        pitch = self.selected_pitch
        self.mapping[pitch] = self.map_var.get()
        self.map_tree.set(str(pitch), 'lane', self.map_var.get())
        self.map_tree.item(str(pitch), tags=())

    def choose_audio(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[('Audio', '*.ogg *.opus *.mp3 *.wav')])
        if path:
            self.audio.set(path)

    def choose_lyrics(self):
        path = filedialog.askopenfilename(parent=self, title='Choose timed lyrics', filetypes=[('Timed lyrics', '*.lrc'), ('All files', '*.*')])
        if path:
            self.lyrics.set(path)

    def choose_output(self):
        folder = filedialog.askdirectory(parent=self, title='Choose a folder for exported songs')
        if folder:
            self.output.set(folder)

    def choose_art(self):
        path = filedialog.askopenfilename(parent=self, title='Choose album art', filetypes=[('Album art', '*.png *.jpg *.jpeg')])
        if path:
            self.album_art.set(path)

    def choose_extra(self):
        role = self.extra_role.get()
        extensions = ' '.join('*'+extension for extension in sorted(EXTRA_TYPES[role][0]))
        path = filedialog.askopenfilename(parent=self, title=f'Choose {role.lower()}', filetypes=[(role, extensions)])
        if path:
            self.extras[role] = Path(path)
            if self.extra_tree.exists(role): self.extra_tree.delete(role)
            self.extra_tree.insert('', 'end', iid=role, values=(role, path))

    def remove_extra(self):
        for role in self.extra_tree.selection():
            self.extras.pop(role, None); self.extra_tree.delete(role)

    def selected_instruments(self):
        if self.score is None: raise AppError('Load a Guitar Pro file first.')
        track = None
        if self.drums_enabled.get():
            index = self.track_combo.current()
            if index < 0: raise AppError('Select a drum track or disable drums.')
            track = self.tracks[index]['index']
        selections = {}
        for role, settings in self.fretted.items():
            if not settings['enabled'].get(): continue
            index = settings['combo'].current()
            if index < 0: raise AppError(f'Choose the GP track for {role}.')
            selections[role] = {'track_index': self.pitched_tracks[index]['index'], 'open_notes': settings['open'].get(), 'intensity_override': settings['override'].get()}
        if track is None and not selections: raise AppError('Enable at least one instrument.')
        return track, selections

    def calculate_intensity(self):
        if self.busy: return
        try:
            track, selections = self.selected_instruments()
            bpm = float(self.song_bpm.get())
            import math
            if not math.isfinite(bpm) or bpm <= 0: raise ValueError()
        except AppError as e:
            messagebox.showerror('Song difficulty', str(e), parent=self)
            return
        except ValueError:
            messagebox.showerror('Song BPM', 'Enter your song BPM first.', parent=self)
            return
        score, mapping = self.score, dict(self.mapping)
        override, drum_override = self.intensity_override.get(), self.drum_intensity_override.get()
        def done(result):
            rating = result[1]['song_intensity']
            self.intensity_info.set(f"Average: {rating['average_selected']:.2f}/6 across {len(rating['components'])} selected parts. Song rating: {rating['selected']}/6. Recalculated at export.")
            components = ' · '.join(f"{role}: {item['selected']}/6" for role,item in rating['components'].items())
            self.status.set('Song difficulty calculated. ' + components)
        self.run_job('Calculating selected instrument difficulties…', lambda: convert_song(score, track, mapping, strict=False, song_bpm=bpm, fretted_tracks=selections, intensity_override=drum_override, song_intensity_override=override, star_power_enabled=False), done)

    def preview_fretted(self, role):
        settings = self.fretted[role]
        index = settings['combo'].current()
        if self.busy or self.score is None or index < 0:
            messagebox.showinfo('Choose a track', f'Load a GP file and select a {role.lower()} track first.', parent=self)
            return
        score, track_index, opens = self.score, self.pitched_tracks[index]['index'], settings['open'].get()
        def done(result):
            details = result[1]
            settings['preview'].delete(*settings['preview'].get_children())
            names = {0:'G', 1:'R', 2:'Y', 3:'B', 4:'O', 7:'Open'}
            for event in details['expert_pattern'][:500]:
                settings['preview'].insert('', 'end', values=(event['tick'], ', '.join(map(str,event['source_pitches'])), ' + '.join(names[lane] for lane in event['lanes'])))
            settings['info'].set(f"Estimated intensity: {details['intensity']['estimated']}/6. Expert: {details['source_positions']} note positions. Preview shows up to 500 positions; full mapping is in the export report.")
            self.status.set(f'{role} preview generated. Confirm the pattern against your recording before using the export.')
        self.run_job(f'Building {role.lower()} fret patterns…', lambda: chart_fretted(score, track_index, role, open_notes=opens), done)

    def export(self):
        if self.busy:
            return
        try:
            track, fretted_tracks = self.selected_instruments()
        except AppError as e:
            messagebox.showerror('Choose instruments', str(e), parent=self)
            return
        try:
            lyrics_offset = int(self.lyrics_offset.get())
            if abs(lyrics_offset) > 3600000:
                raise ValueError()
            offset = int(self.offset.get())
            if abs(offset) > 3600000:
                raise ValueError()
            if not self.output.get().strip():
                raise AppError('Choose an output folder.')
        except ValueError:
            messagebox.showerror('Timing adjustment', 'Enter a whole number of milliseconds between -3600000 and 3600000.', parent=self)
            return
        except AppError as e:
            messagebox.showerror('Output folder', str(e), parent=self)
            return
        if not self.song_bpm.get().strip():
            self.ask_song_bpm()
            if not self.song_bpm.get().strip():
                return
        try:
            import math
            song_bpm = float(self.song_bpm.get())
            if not math.isfinite(song_bpm) or song_bpm <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror('Song BPM', 'Enter a positive, finite song BPM.', parent=self)
            return
        score, mapping = self.score, dict(self.mapping)
        parent = Path(self.output.get()).expanduser()
        opts = dict(audio=Path(self.audio.get()).expanduser() if self.audio.get().strip() else None,
                    offset_ms=offset, strict=self.strict.get(), dynamics=self.dynamics.get(),
                    title=self.title_var.get().strip(), artist=self.artist_var.get().strip())
        opts.update(song_bpm=song_bpm, lyrics=Path(self.lyrics.get()).expanduser() if self.lyrics.get().strip() else None, lyrics_offset_ms=lyrics_offset)
        opts.update(properties={**{key: value.get() for key, value in self.properties.items()}, 'modchart': str(self.modchart.get()), 'video_loop': str(self.video_loop.get())},
                    intensity_override=self.drum_intensity_override.get(),
                    song_intensity_override=self.intensity_override.get(),
                    star_power_enabled=self.star_power_enabled.get(), extras=dict(self.extras),
                    album_art=Path(self.album_art.get()).expanduser() if self.album_art.get().strip() else None)
        opts['fretted_tracks'] = fretted_tracks
        def done(result):
            self.last_export, report = result
            intensity = report['intensity']
            song_rating = report['song_intensity']
            self.intensity_info.set(f"Average: {song_rating['average_selected']:.2f}/6. Song rating: {song_rating['selected']}/6 ({'manual override' if song_rating['overridden'] else 'averaged'}).")
            text = f"Exported {report['exported_hits']} hits from {report['source_hits']} source hits. {report['double_bass']['tagged_hits']} Double Bass hits."
            if 'Drums' not in report['instruments']:
                text = 'Exported selected five-fret instruments.'
            text += f"\nSong difficulty: {song_rating['selected']}/6; selected-part average {song_rating['average_selected']:.2f}/6."
            counts = report['downchart']['difficulties']
            if counts:
                text += '\n' + ' · '.join(f"{name}: {counts[name]['hits']} drum hits" for name in ('Expert', 'Hard', 'Medium', 'Easy'))
            if 'Drums' in report['instruments']:
                text += f"\nDrum intensity: {intensity['selected']}/6 ({'manual override' if intensity['overridden'] else 'estimated'})."
            for role, details in report['instruments'].items():
                if role in TRACK_NAMES:
                    text += f"\n{role}: {details['difficulties']['Expert']['positions']} Expert positions, intensity {details['intensity']['selected']}/6."
                    self.fretted[role]['info'].set(f"Exported intensity {details['intensity']['selected']}/6; estimated {details['intensity']['estimated']}/6.")
            if report['star_power']['enabled']:
                total_phrases = sum(tier['phrase_count'] for part in report['star_power']['instruments'].values() for tier in part.values())
                text += f'\nStar Power: {total_phrases} phrases across the selected parts and difficulties.'
            if report['lyrics']:
                text += f"\nLyrics: {report['lyrics']['phrases']} lines, {report['lyrics']['lyric_events']} timed events."
            self.status.set(text + ' Scan this folder in Clone Hero. See conversion_report.json for details.')
            extra = '\n\n' + '\n'.join(report['issues']) if report['issues'] else ''
            if report['lyrics']:
                extra += '\n\nLyrics review: ' + '\n'.join(report['lyrics']['warnings'])
            if report['ignored']:
                extra += '\nIntentionally ignored hits: ' + str(sum(report['ignored'].values()))
            if opts['audio'] is None:
                extra += '\nA silent practice track is included; add music when you have a matching recording.'
            if report['downchart']['warnings']:
                extra += '\n\nReduction review: ' + '\n'.join(report['downchart']['warnings'])
            if report['extras']['warnings']:
                extra += '\n\nMedia: ' + '\n'.join(report['extras']['warnings'])
            if fretted_tracks:
                extra += '\n\nFive-fret patterns are musical reductions. Review phrase resets and chord shapes; details are in conversion_report.json.'
            messagebox.showinfo('Selected instruments exported', text + '\n\n' + str(self.last_export) + extra, parent=self)
        self.run_job('Checking every hit and writing your Clone Hero song folder…',
                     lambda: export_song(score, track, mapping, parent, **opts), done)

    def open_export(self):
        if self.last_export and self.last_export.is_dir():
            if os.name == 'nt':
                os.startfile(self.last_export)
            else:
                webbrowser.open(self.last_export.as_uri())
        else:
            messagebox.showinfo('No export yet', 'Export a chart first.', parent=self)


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--verify':
        # Exercise the packaged reader and exporter without opening a window.
        import json
        from core import ROOT, convert
        destination = Path(sys.argv[2]).resolve()
        try:
            score = read_gp(ROOT / 'demo.gp')
            lyric_path = destination.parent / 'verify-lyrics.lrc'
            lyric_path.write_text('[00:01.00]Line timing\n[00:02.00]<00:02.00>Word <00:02.50>timing<00:03.00>', encoding='utf8')
            folder, report = export_song(score, 0, DEFAULT_MAP, destination.parent / 'verify-songs', lyrics=lyric_path,
                                         properties={'album': 'Verification album', 'charter': APP_NAME}, intensity_override=2)
            fast_score = json.loads(json.dumps(score))
            fast_score['tracks'][0]['notes'] = [{'tick': t, 'pitch': 36, 'velocity': 95, 'length': 120}
                                               for t in range(0, 1440, 240)]
            fast_chart, fast_report = convert(fast_score, 0, DEFAULT_MAP, song_bpm=120)
            exported_chart = (folder / 'notes.chart').read_text(encoding='utf8')
            all_tiers = all(f'[{difficulty}Drums]' in exported_chart for difficulty in ('Expert', 'Hard', 'Medium', 'Easy'))
            lyrics_verified = report['lyrics']['lyric_events'] == 3 and 'lyric Line timing' in exported_chart and 'lyric Word' in exported_chart and 'lyric timing' in exported_chart
            from lyrics import parse_lrc, chart_lyrics, adjusted_lrc
            repaired = parse_lrc('[00:01.00]First <00:00.50>second <00:05.00>third\n[00:04.00]Next')
            _, repair_report = chart_lyrics(score, repaired)
            repairs_verified = len(repair_report['repairs']) >= 2 and len(parse_lrc(adjusted_lrc(repaired))[0]) == 2
            ini = (folder / 'song.ini').read_text(encoding='utf8')
            properties_verified = 'album = Verification album' in ini and 'diff_drums_real = 2' in ini and report['intensity']['overridden']
            fretted_score = read_gp(ROOT / 'demo-fretted.gp')
            selections = {role: {'track_index': index, 'intensity_override': index+1} for index,role in enumerate(('Guitar','Bass','Rhythm'))}
            import base64
            from core import write_silence
            image_path = destination.parent / 'verify-cover.png'
            image_path.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/WZkAAAAASUVORK5CYII='))
            preview_path = destination.parent / 'verify-preview.wav'
            write_silence(preview_path, 0.25)
            fretted_folder, fretted_report = export_song(fretted_score, None, {}, destination.parent / 'verify-songs', fretted_tracks=selections,
                extras={'Photo background': image_path, 'Preview audio': preview_path}, album_art=image_path)
            fretted_chart = (fretted_folder / 'notes.chart').read_text(encoding='utf8')
            fretted_ini = (fretted_folder / 'song.ini').read_text(encoding='utf8')
            fretted_verified = all(f'[{difficulty}{suffix}]' in fretted_chart for suffix in ('Single','DoubleBass','DoubleRhythm') for difficulty in ('Expert','Hard','Medium','Easy')) and '[ExpertDrums]' not in fretted_chart and 'diff_rhythm = 3' in fretted_ini
            star_power_verified = all(tier['phrase_count'] > 0 for r in (report, fretted_report) for part in r['star_power']['instruments'].values() for tier in part.values())
            media_verified = all((fretted_folder/name).is_file() for name in ('background.png','album.png','preview.wav'))
            song_average_verified = fretted_report['song_intensity']['average_selected'] == 2 and 'diff_band = 2' in fretted_ini
            release_verified = report.get('application') == {'name': APP_NAME, 'version': RELEASE_VERSION} and (ROOT/'assets'/'chart-starter-logo.png').is_file() and (ROOT/'HELP.md').is_file()
            destination.write_text(json.dumps({'release_verified': release_verified, 'ok': release_verified and report['exported_hits'] == 80 and
                                                fast_report['double_bass']['tagged_hits'] == 3 and
                                                '240 = N 32 0' in fast_chart and all_tiers and lyrics_verified and repairs_verified and properties_verified and fretted_verified and star_power_verified and media_verified and song_average_verified,
                                                'star_power_verified': star_power_verified, 'media_verified': media_verified, 'song_average_verified': song_average_verified,
                                                'fretted_instruments_verified': fretted_verified,
                                                'song_properties_verified': properties_verified,
                                                'lyrics_repairs_verified': repairs_verified,
                                                'lyrics_verified': lyrics_verified,
                                                'all_difficulties_verified': all_tiers,
                                                'folder': str(folder), 'report': report,
                                                'double_bass_verification': fast_report['double_bass']}, indent=2), encoding='utf8')
        except Exception as e:
            destination.write_text(json.dumps({'ok': False, 'error': str(e)}), encoding='utf8')
            sys.exit(1)
    else:
        App().mainloop()
