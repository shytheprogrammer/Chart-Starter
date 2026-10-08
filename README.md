# Chart Starter 1.0

An offline Windows app for starting Clone Hero charts from local Guitar Pro scores.

## Start

Extract the complete ZIP into a new folder. Run **Start.cmd**, or **Windows/ChartStarter.exe**. Keep the executable and its `_internal` folder together. The Windows release includes its runtimes; no Python installation is required.

## Create a chart

1. Load a GP score and enter its song BPM.
2. Choose tracks in Drums, Guitar, Bass and Rhythm and enable the parts you want.
3. Review drum mapping and pitched-pattern previews.
4. Add a matching recording, optional LRC lyrics, song properties, cover art and extras.
5. Calculate the song rating or choose overrides, then export.
6. Scan the exported song folder in Clone Hero and playtest the result.

The **Help** tab includes searchable, detailed instructions for every feature. The same guide is provided in **[HELP.md](HELP.md)** for reading outside the app.

## Included features

Local GP/GPX and legacy GP track import; drum mapping, Double Bass and dynamics; Guitar/Bass/Rhythm five-fret reductions; all four difficulties; song properties and estimated overall/individual ratings with overrides; standard/enhanced LRC and automatic timing repairs; Star Power; cover art, video/photo backgrounds, preview/stem audio, and separately installable Custom extras.

Automatic fret mapping, difficulty reductions/ratings, lyric repairs and Star Power are charting aids. Review timing and playing quality against the matching recording. Videos/audio are copied without transcoding. Custom highways, icons and colors need separate installation as described in the exported Extras/INSTALL.txt.

## Logo and licenses

The original logo is **[assets/chart-starter-logo.png](assets/chart-starter-logo.png)**. It was generated with the built-in image-generation tool; the complete prompt is in **[assets/logo-design.txt](assets/logo-design.txt)**.

The application uses alphaTab, Node.js, Python and Tkinter. Included runtime/license files accompany the release. `demo.gp` and `demo-fretted.gp` are original generated examples.

## Format references

[Official Clone Hero song.ini guide](https://wiki.clonehero.net/books/guides-and-tutorials/page/songini-guide), [custom content](https://wiki.clonehero.net/books/clone-hero-manual/page/other-custom-content), and [chart format documentation](https://solamint.github.io/GuitarGame_ChartFormats/).

Source users can launch `python app.py` with Python 3.10+; bundled `vendor/node.exe` is used for GP reading on Windows. No additional Python packages are required by the application.
