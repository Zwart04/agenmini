"""Lossless documentation stills and a high-quality, labelled screenshot tour.

Requires Pillow and an explicit ffmpeg executable. These are documentation
build tools; they are not new application/runtime dependencies.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / 'docs/screenshots'


def export(ffmpeg):
    manifest = json.loads((MEDIA / 'capture.json').read_text())
    for entry in manifest['screenshots']:
        file = MEDIA / entry['name']
        with Image.open(file) as image:
            assert image.format == 'PNG' and image.size == (entry['width'], entry['height'])
            image.save(file, optimize=True, compress_level=9)
    for name in ('workbench-desktop', 'workbench-mobile'):
        with Image.open(MEDIA / (name+'.png')) as image:
            image.save(MEDIA / (name+'.webp'), lossless=True, method=6)
        with Image.open(MEDIA / (name+'.png')) as original, Image.open(MEDIA / (name+'.webp')) as packed:
            assert original.convert('RGB').tobytes() == packed.convert('RGB').tobytes()
    names = ['chat-desktop.png','workbench-desktop.png','workspace-desktop.png','providers-desktop.png','workbench-light.png']
    with tempfile.TemporaryDirectory(prefix='media-frames-', dir=ROOT / '.local-tools') as folder:
        folder = Path(folder)
        gif_frames=[]
        for index, name in enumerate(names):
            with Image.open(MEDIA / name) as source:
                frame = source.convert('RGB').resize((1920,1280), Image.Resampling.LANCZOS)
                frame.save(folder / f'frame-{index:02d}.png')
                gif_frames.append(source.convert('RGB').resize((1440,960), Image.Resampling.LANCZOS).quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE))
        gif_frames[0].save(MEDIA/'preview.gif',save_all=True,append_images=gif_frames[1:],duration=3200,loop=0,optimize=True,disposal=2)
        subprocess.run([str(ffmpeg),'-y','-hide_banner','-loglevel','error','-framerate','1/3.2','-i',str(folder/'frame-%02d.png'),'-vf','fps=24','-c:v','libx264','-preset','slow','-crf','15','-pix_fmt','yuv420p','-movflags','+faststart',str(MEDIA/'preview.mp4')],check=True)
        subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-i',str(MEDIA/'preview.mp4'),'-f','null','-'],check=True)
    with Image.open(MEDIA/'preview.gif') as gif:
        assert gif.size==(1440,960) and gif.n_frames==len(names)
    print('PASS PNG signatures/dimensions, pixel-identical lossless WebP, 1440px GIF and decodable 1920px MP4')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',type=Path,required=True)
    export(parser.parse_args().ffmpeg)
