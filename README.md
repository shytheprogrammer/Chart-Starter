<img width="250" height="1250" alt="chart-starter-logo" src="https://github.com/user-attachments/assets/a97247c2-fa90-4f04-aed5-1724605d3b20" />

# Chart Starter 1.0

An offline Windows app for starting Clone Hero charts from local Guitar Pro scores.

<img width="1919" height="1031" alt="image" src="https://github.com/user-attachments/assets/14105631-0b00-4c7a-a92a-c02d5434fd09" />

## Start

Extract the complete ZIP into a new folder. Run **Start.cmd**, or **Windows/ChartStarter.exe**. Keep the executable and its `_internal` folder together. The Windows release includes its runtimes; no Python installation is required.

## Create a chart

1. Load a GP score and enter its song BPM.
2. Choose tracks in Drums, Guitar, Bass and Rhythm and enable the parts you want.
3. Review drum mapping and pitched-pattern previews.
4. Add a matching recording, optional LRC lyrics, song properties, cover art and extras.
5. Calculate the song rating or choose overrides, then export.
6. Open the exported chart in Moonscraper, align everything with the matching recording, and review all parts. Then scan the song folder in Clone Hero and playtest it.

The **Help** tab includes searchable, detailed instructions for every feature. The same guide is provided in **[HELP.md](HELP.md)** for reading outside the app.

## Included features

Local GP/GPX and legacy GP track import; drum mapping, Double Bass and dynamics; Guitar/Bass/Rhythm five-fret reductions; all four difficulties; song properties and estimated overall/individual ratings with overrides; standard/enhanced LRC and automatic timing repairs; Star Power; cover art, video/photo backgrounds, preview/stem audio, and separately installable Custom extras.

Automatic fret mapping, difficulty reductions/ratings, lyric repairs and Star Power are charting aids. Review timing and playing quality against the matching recording. Videos/audio are copied without transcoding. Custom highways, icons and colors need separate installation as described in the exported Extras/INSTALL.txt.

## Logo and third-party licenses

The original logo is **[assets/chart-starter-logo.png](assets/chart-starter-logo.png)**. 

The application uses alphaTab, Node.js, Python and Tkinter. Included runtime/license files accompany the release. `demo.gp` and `demo-fretted.gp` are original practice examples.

## Format references

[Official Clone Hero song.ini guide](https://wiki.clonehero.net/books/guides-and-tutorials/page/songini-guide), [custom content](https://wiki.clonehero.net/books/clone-hero-manual/page/other-custom-content), and [chart format documentation](https://solamint.github.io/GuitarGame_ChartFormats/).

Source users can launch `python app.py` with Python 3.10+; bundled `vendor/node.exe` is used for GP reading on Windows. No additional Python packages are required by the application.

## Finding input files

Search for Guitar Pro tabs on [Songsterr](https://www.songsterr.com/), copy the song URL, and paste it into [Songsterr Downloader](https://www.songsterr-downloader.com/) to save a Guitar Pro file. Find available LRC lyric files on [Lyricsify](https://www.lyricsify.com/). These websites are used separately in your browser; Chart Starter loads local files. Choose files matching your recording and align everything in Moonscraper after export.

## Run the source

Install Python 3.10+ with Tkinter and Node.js, with `node` available on PATH. Run `python app.py` from the repository folder. The app needs no third-party Python packages. Run the test suite with `python -m unittest discover`.

The GitHub source package excludes compiled Windows builds, bundled runtime executables, caches and design notes. Windows users can use the separate packaged release.
