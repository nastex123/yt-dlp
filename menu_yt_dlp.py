#!/usr/bin/env python3
"""Menú interactivo para ejecutar la versión local de yt-dlp."""

import os
import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent


def ask(prompt, default=''):
    suffix = f' [{default}]' if default else ''
    return input(f'{prompt}{suffix}: ').strip() or default


def yes(prompt, default=True):
    while True:
        value = ask(f'{prompt} ({"S/n" if default else "s/N"})').lower()
        if not value:
            return default
        if value in ('s', 'si', 'sí'):
            return True
        if value in ('n', 'no'):
            return False
        print('Responde s o n.')


def choose(prompt, choices, default='1'):
    for key, label in choices.items():
        print(f'  {key}. {label}')
    while True:
        value = ask(prompt, default)
        if value in choices:
            return value
        print('Selecciona una opción válida.')


def run(args, validate_audio=False):
    print('\nEjecutando yt-dlp...\n', flush=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        paths = Path(temp_dir) / 'archivos.txt'
        reporting = ['--print-to-file', 'after_move:filepath', str(paths)] if validate_audio else []
        result = subprocess.run([sys.executable, '-m', 'yt_dlp', *reporting, *args], cwd=ROOT, check=False)
        if validate_audio and paths.exists():
            for path in paths.read_text(encoding='utf-8').splitlines():
                if not music_cover(path):
                    square_cover(path)
                validate_tags(path)
    print(f'\nProceso terminado con código {result.returncode}.')


def music_cover(path):
    """Usa la portada de la canción solo cuando coincide el identificador de YouTube."""
    try:
        from ytmusicapi import YTMusic
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format_tags', '-of', 'json', path],
            capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        tags = {k.lower(): v for k, v in json.loads(probe.stdout).get('format', {}).get('tags', {}).items()}
        source = urlparse(tags.get('purl') or tags.get('comment') or '')
        if source.hostname not in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be'):
            return False
        video_id = source.path.lstrip('/') if source.hostname == 'youtu.be' else parse_qs(source.query).get('v', [''])[0]
        if not video_id or not tags.get('title'):
            return False
        artist = tags.get('artist', '').split(',')[0]
        print('Buscando la portada del álbum en YouTube Music...')
        songs = YTMusic().search(f"{artist} {tags['title']}", filter='songs', limit=20)
        match = next((song for song in songs if song.get('videoId') == video_id and song.get('thumbnails')), None)
        if not match:
            print('No se encontró una portada para el identificador exacto de la canción.')
            return False
        thumbnail = max(match['thumbnails'], key=lambda item: item.get('width', 0) * item.get('height', 0))['url']
        if urlparse(thumbnail).hostname not in ('yt3.googleusercontent.com', 'lh3.googleusercontent.com'):
            print('La dirección de la portada no es reconocida.')
            return False
        thumbnail = thumbnail.split('=')[0] + '=w600-h600-l90-rj'
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'cover'
            with urlopen(thumbnail, timeout=15) as response:
                image.write_bytes(response.read(10 * 1024 * 1024 + 1))
            if image.stat().st_size > 10 * 1024 * 1024:
                raise ValueError('La portada supera el tamaño permitido')
            with tempfile.NamedTemporaryFile(suffix='.mp3', dir=str(Path(path).resolve().parent), delete=False) as temp:
                temp_path = temp.name
            try:
                result = subprocess.run([
                    'ffmpeg', '-y', '-v', 'error', '-i', path, '-i', str(image),
                    '-map', '0:a', '-map', '1:v:0', '-map_metadata', '0', '-c:a', 'copy',
                    '-c:v', 'mjpeg', '-disposition:v:0', 'attached_pic',
                    '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)',
                    '-id3v2_version', '3', temp_path,
                ], capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
                if result.returncode:
                    print(f'No se pudo incrustar la portada: {result.stderr.strip()}')
                    return False
                os.replace(temp_path, path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        print('Portada del álbum de YouTube Music incrustada.')
        return True
    except Exception as error:
        print(f'No se pudo obtener la portada de YouTube Music: {error}')
        return False


def square_cover(path):
    """Recorta la portada incrustada sin recodificar el audio ni alterar el original al fallar."""
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
             'stream=width,height:stream_disposition=attached_pic', '-of', 'json', path],
            capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
        streams = json.loads(probe.stdout).get('streams', []) if probe.returncode == 0 else []
        if not streams or not streams[0].get('disposition', {}).get('attached_pic'):
            print('No se encontró una portada incrustada para recortar.')
            return
        width, height = streams[0].get('width'), streams[0].get('height')
        if not width or not height:
            print('No se pudieron comprobar las dimensiones de la portada.')
            return
        if width == height:
            print(f'La portada ya es cuadrada ({width} × {height}).')
            return
        with tempfile.NamedTemporaryFile(suffix='.mp3', dir=str(Path(path).resolve().parent), delete=False) as temp:
            temp_path = temp.name
        try:
            result = subprocess.run([
                'ffmpeg', '-y', '-v', 'error', '-i', path,
                '-filter_complex', "[0:v:0]crop='min(iw,ih)':'min(iw,ih)'[cover]",
                '-map', '0:a', '-map', '[cover]', '-map_metadata', '0',
                '-c:a', 'copy', '-c:v', 'mjpeg', '-disposition:v:0', 'attached_pic',
                '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)',
                '-id3v2_version', '3', temp_path,
            ], capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
            if result.returncode:
                print(f'No se pudo recortar la portada: {result.stderr.strip()}')
                return
            os.replace(temp_path, path)
            print(f'Portada recortada al centro: {min(width, height)} × {min(width, height)}.')
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except (OSError, json.JSONDecodeError) as error:
        print(f'No se pudo procesar la portada: {error}')


def validate_tags(path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format_tags:stream=codec_type',
             '-of', 'json', path], capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
        data = json.loads(result.stdout) if result.returncode == 0 else {}
    except (OSError, json.JSONDecodeError):
        data = {}
    if not data:
        print(f'No se pudieron verificar las etiquetas de {path}.')
        return
    tags = {key.lower(): str(value) for key, value in data.get('format', {}).get('tags', {}).items()}
    print(f'\nMetadatos guardados en {path}:')
    for label, keys in [('Título', ('title',)), ('Artista', ('artist',)), ('Álbum', ('album',)), ('Año', ('date', 'year'))]:
        print(f"  {label}: {next((tags[key] for key in keys if tags.get(key)), 'No disponible')}")
    print('  Portada:', 'Sí' if any(stream.get('codec_type') == 'video' for stream in data.get('streams', [])) else 'No disponible')


def extra_args():
    print('\nOpciones adicionales: escribe un argumento por línea; deja una línea vacía para terminar.')
    print('Ejemplo: escribe --limit-rate en una línea y 2M en la siguiente.')
    args = []
    while True:
        arg = input('Argumento: ').strip()
        if not arg:
            return args
        args.append(arg)


def url_input():
    while True:
        url = ask('Enlace (o deja vacío para volver)')
        if not url:
            return None
        if not url.startswith('-'):
            return url
        print('El enlace no puede comenzar con un guion.')


def find_music(url):
    """Busca canciones en YouTube Music y deja que el usuario elija."""
    def inspect(args):
        process = subprocess.run(
            [sys.executable, '-m', 'yt_dlp', '--ignore-config', *args],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', check=False)
        if process.returncode:
            print(process.stderr.strip() or 'No se pudo completar la búsqueda.')
            return None
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError:
            print('No se pudo interpretar la respuesta de yt-dlp.')
            return None

    print('\nBuscando información del video...', flush=True)
    info = inspect(['--dump-single-json', '--no-playlist', '--', url])
    if not info:
        return None
    title = info.get('track') or info.get('title') or ''
    artist = info.get('artist') or info.get('uploader') or ''
    query = f'{artist} {title}'.strip()
    if not query:
        return None
    print('Buscando canciones...', flush=True)
    search_url = f'https://music.youtube.com/search?q={quote_plus(query)}#songs'
    results = inspect(['--flat-playlist', '--playlist-end', '10', '--dump-single-json', '--', search_url])
    entries = [entry for entry in (results or {}).get('entries', []) if entry and entry.get('id')]
    if not entries:
        print('No se encontraron canciones. Puedes usar el enlace original.')
        return None
    first_url = f"https://music.youtube.com/watch?v={entries[0]['id']}"
    candidate = inspect(['--dump-single-json', '--no-playlist', '--', first_url])
    def normalized(value):
        return ' '.join(''.join(char for char in unicodedata.normalize('NFKD', value.casefold())
                                if not unicodedata.combining(char)).split())
    if candidate:
        candidate_title = candidate.get('track') or candidate.get('title') or ''
        original_duration, candidate_duration = info.get('duration'), candidate.get('duration')
        original_artist = normalized(info.get('artist') or info.get('uploader') or '').replace(' - topic', '')
        candidate_artist = normalized(candidate.get('artist') or candidate.get('uploader') or '')
        durations_match = (isinstance(original_duration, (int, float))
                           and isinstance(candidate_duration, (int, float))
                           and abs(original_duration - candidate_duration) <= 35)
        if (len(normalized(candidate_title)) >= 4 and normalized(candidate_title) in normalized(title)
                and len(original_artist) >= 3 and original_artist in candidate_artist and durations_match):
            print(f"Canción encontrada automáticamente: {candidate_title} — {candidate.get('artist') or candidate.get('uploader') or 'artista no disponible'}")
            return first_url
    print('No hay una coincidencia suficientemente clara; elige una opción:')
    choices = {}
    for index, entry in enumerate(entries, 1):
        duration = entry.get('duration')
        length = f' ({int(duration) // 60}:{int(duration) % 60:02d})' if isinstance(duration, (int, float)) else ''
        choices[str(index)] = f"{entry.get('title', 'Sin título')} — {entry.get('artist') or entry.get('uploader') or 'Artista desconocido'}{length}"
    choices['0'] = 'Usar el enlace original'
    selected = choose('Elige la canción', choices, '0')
    if selected == '0':
        return None
    return f"https://music.youtube.com/watch?v={entries[int(selected) - 1]['id']}"


def configure_download(kind, url):
    if kind == '1':
        print('Configuración automática: MP3, metadatos, portada y lista completa si existe.')
        return [
            '-x', '--audio-format', 'mp3', '--embed-metadata', '--embed-thumbnail',
            '--no-write-info-json', '--yes-playlist',
            '-o', '%(playlist_title|.)s/%(title)s.%(ext)s', '--', url,
        ]
    args = ['-o', '%(title)s.%(ext)s']
    if kind == '2':
        quality = choose('Calidad', {'1': 'Mejor disponible', '2': 'Hasta 1080p', '3': 'Hasta 720p', '4': 'Elegir ID de formato'})
        if quality in ('2', '3'):
            height = '1080' if quality == '2' else '720'
            args += ['-f', f'bestvideo[height<={height}]+bestaudio/best[height<={height}]']
        elif quality == '4':
            format_id = ask('ID de formato (consulta primero la opción 3 del menú)')
            if format_id:
                args += ['-f', format_id]
        if yes('¿Descargar subtítulos si están disponibles?', False):
            args += ['--write-subs', '--sub-langs', ask('Idiomas separados por coma', 'es.*,en.*')]
            if yes('¿Incrustar subtítulos?', True):
                args.append('--embed-subs')

    if yes('¿Incrustar metadatos?', True):
        args.append('--embed-metadata')
    if yes('¿Incrustar portada?', True):
        args.append('--embed-thumbnail')
    if yes('¿Guardar también los metadatos en JSON?', False):
        args.append('--write-info-json')
    args.append('--yes-playlist' if yes('¿Descargar toda la lista si el enlace pertenece a una?', False) else '--no-playlist')
    folder = ask('Carpeta de destino (vacío: carpeta actual)')
    if folder:
        args += ['-P', os.path.abspath(os.path.expanduser(folder))]
    if yes('¿Usar las cookies de un navegador?', False):
        browser = ask('Navegador (chrome, firefox, edge, etc.)', 'chrome')
        args += ['--cookies-from-browser', browser]
    if yes('¿Añadir opciones avanzadas?', False):
        args.extend(extra_args())
    return [*args, '--', url]


def main():
    print('=== Menú interactivo de yt-dlp ===')
    print('Las descargas requieren conexión a Internet; algunas opciones requieren FFmpeg.')
    while True:
        print()
        action = choose('Elige una opción', {
            '1': 'Descargar audio', '2': 'Descargar video', '3': 'Ver formatos disponibles',
            '4': 'Ver información del enlace', '5': 'Usar opciones avanzadas',
            '6': 'Ver ayuda completa de yt-dlp', '7': 'Corregir portada de un MP3', '0': 'Salir',
        })
        if action == '0':
            return
        if action == '6':
            run(['--help'])
            continue
        if action == '7':
            path = ask('Ruta del MP3').strip('"')
            if path and Path(path).is_file() and Path(path).suffix.lower() == '.mp3':
                if not music_cover(path):
                    print('Se conserva la portada actual.')
                validate_tags(path)
            else:
                print('No se encontró el archivo MP3.')
            continue
        url = url_input()
        if not url:
            continue
        if action in ('1', '2'):
            parsed = urlparse(url)
            if (action == '1' and parsed.hostname in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be')
                    and 'list' not in parse_qs(parsed.query)):
                url = find_music(url) or url
            args = configure_download(action, url)
        elif action == '3':
            args = ['--list-formats', '--no-playlist', '--', url]
        elif action == '4':
            args = ['--dump-single-json', '--no-playlist', '--', url]
        else:
            args = [*extra_args(), '--', url]
        run(args, validate_audio=action == '1')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nHasta luego.')
