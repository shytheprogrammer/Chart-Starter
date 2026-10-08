"""Package supported song assets and separately installable Clone Hero custom content."""
import shutil
from pathlib import Path

IMAGES = {'.png','.jpg','.jpeg'}
VIDEOS = {'.mp4','.avi','.webm','.ogv','.mpeg'}
AUDIO = {'.ogg','.opus','.mp3','.wav'}
# UI key: (extensions, song filename stem or Custom subfolder, kind)
EXTRA_TYPES = {
    'Photo background': (IMAGES, 'background', 'song'),
    'Video background': (VIDEOS, 'video', 'song'),
    'Preview audio': (AUDIO, 'preview', 'song'),
    'Guitar stem': (AUDIO, 'guitar', 'song'), 'Bass stem': (AUDIO, 'bass', 'song'),
    'Rhythm stem': (AUDIO, 'rhythm', 'song'), 'Drums stem': (AUDIO, 'drums', 'song'),
    'Kick / drums_1 stem': (AUDIO, 'drums_1', 'song'), 'Snare / drums_2 stem': (AUDIO, 'drums_2', 'song'),
    'Toms / drums_3 stem': (AUDIO, 'drums_3', 'song'), 'Cymbals / drums_4 stem': (AUDIO, 'drums_4', 'song'),
    'Vocals stem': (AUDIO, 'vocals', 'song'), 'Keys stem': (AUDIO, 'keys', 'song'),
    'Crowd audio': (AUDIO, 'crowd', 'song'),
    'Highway image': (IMAGES, 'Highways', 'custom'),
    'Highway video': ({'.webm'}, 'Video Highways', 'custom'),
    'Highway video config': ({'.ini'}, 'Video Highways', 'config'),
    'Song icon image': (IMAGES, 'Game Icons', 'custom'),
    'Color profile': ({'.ini'}, 'Colors', 'custom'),
}

def validate_extras(extras):
    result = {}
    for role, value in (extras or {}).items():
        if role not in EXTRA_TYPES: raise ValueError(f'Unsupported extra: {role}')
        path = Path(value)
        allowed, _, _ = EXTRA_TYPES[role]
        if not path.is_file() or path.suffix.lower() not in allowed:
            raise ValueError(f'{role}: choose an existing file with one of these extensions: {", ".join(sorted(allowed))}.')
        result[role] = path
    if 'Drums stem' in result and any('drums_' in role for role in result):
        raise ValueError('Choose either a combined Drums stem or numbered drum stems, not both.')
    if 'Highway video config' in result and 'Highway video' not in result:
        raise ValueError('Choose the highway video that belongs to its config file.')
    return result

def package_extras(stage, extras):
    files, warnings = [], []
    for role, path in extras.items():
        _, stem, kind = EXTRA_TYPES[role]
        extension = '.jpg' if path.suffix.lower() == '.jpeg' else path.suffix.lower()
        if kind == 'song':
            destination = stage/(stem+extension)
        elif role in {'Highway video','Highway video config'}:
            destination = stage/'Extras'/'Custom'/'Video Highways'/'Chart highway'/('config.ini' if kind == 'config' else 'highway.webm')
        else:
            destination = stage/'Extras'/'Custom'/stem/path.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        files.append({'type': role, 'source_file': path.name, 'export_file': destination.relative_to(stage).as_posix(), 'automatic_song_asset': kind == 'song'})
    if any('video' in role.lower() for role in extras):
        warnings.append('Videos are copied without transcoding. Check the codec: VP8 WebM is portable; Windows MP4 should use H.264. Highway video requires VP8 WebM.')
    if any('stem' in role for role in extras):
        warnings.append('Use synchronized stems and a backing-only main audio track to avoid doubling the full mix.')
    if any(EXTRA_TYPES[role][2] != 'song' for role in extras):
        warnings.append('Files under Extras/Custom need installation into Clone Hero’s Custom folder and selection in game. They are not automatically applied by this song.')
        (stage/'Extras'/'INSTALL.txt').write_text('Copy the contents of Custom into Clone Hero’s Custom folder (normally Documents/Clone Hero/Custom on Windows, or PlayerData/Custom for a portable install). Restart Clone Hero or scan Custom Content, then select your highway/color profile in game. Song icons use the icon name from song.ini. Highway images/videos should be 512x1024; animated highways require VP8 WebM. Icons should be square, 64–128 pixels. Existing installed files should be reviewed before copying over them.\n',encoding='utf8')
    return {'files': files, 'warnings': warnings}
