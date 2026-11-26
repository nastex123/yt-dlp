#!/usr/bin/env python3
"""Interfaz de terminal para las funciones de descarga de yt-dlp."""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import menu_yt_dlp as core


DATA_DIR = Path(os.getenv('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'yt-dlp-menu'
SETTINGS_PATH = DATA_DIR / 'configuracion.json'
HISTORY_PATH = DATA_DIR / 'historial.json'
DEFAULTS = {
    'destino': str(core.ROOT),
    'metadatos': True,
    'portada': True,
    'lista': True,
    'navegador': '',
}


def read_json(path, fallback):
    try:
        with path.open(encoding='utf-8') as stream:
            value = json.load(stream)
        if isinstance(value, type(fallback)):
            return value
    except (OSError, ValueError):
        pass
    return fallback.copy()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
        tmp = stream.name
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        except Exception:
            os.unlink(tmp)
            raise
    try:
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def heading(title):
    print(f'\n{"=" * 60}\n {title}\n{"=" * 60}')


def checked_url():
    return core.url_input()


def dependencies():
    heading('DEPENDENCIAS')
    print(f'Python: {sys.version.split()[0]} ({sys.executable})')
    for name in ('ffmpeg', 'ffprobe'):
        location = shutil.which(name)
        print(f'{name}: {location or "NO ENCONTRADO en PATH"}')
    try:
        import ytmusicapi  # noqa: F401
        print('ytmusicapi: disponible')
    except ImportError:
        print('ytmusicapi: falta; instala con python -m pip install ytmusicapi')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        print('Instala FFmpeg y agrega ffmpeg y ffprobe al PATH para convertir y verificar audio.')


def audio_args(url, settings):
    args = ['-x', '--audio-format', 'mp3', '--no-write-info-json']
    args.append('--embed-metadata' if settings['metadatos'] else '--no-embed-metadata')
    args.append('--embed-thumbnail' if settings['portada'] else '--no-embed-thumbnail')
    args.append('--yes-playlist' if settings['lista'] else '--no-playlist')
    args += ['-P', settings['destino'], '-o', '%(playlist_title|.)s/%(title)s.%(ext)s']
    if settings['navegador']:
        args += ['--cookies-from-browser', settings['navegador']]
    return [*args, '--', url]


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def execute(job):
    print('\nIniciando descarga. Pulsa Ctrl+C para cancelar esta descarga.\n', flush=True)
    with tempfile.TemporaryDirectory() as folder:
        paths = Path(folder) / 'archivos.txt'
        command = [sys.executable, '-m', 'yt_dlp', '--newline', '--print-to-file',
                   'after_move:filepath', str(paths), *job['args']]
        kwargs = {'cwd': core.ROOT}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs['start_new_session'] = True
        process = subprocess.Popen(command, **kwargs)
        try:
            code = process.wait()
        except KeyboardInterrupt:
            stop_process(process)
            print('\nDescarga cancelada. Es posible que queden archivos parciales.')
            code = None
        files = paths.read_text(encoding='utf-8').splitlines() if paths.exists() else []
    for path in files:
        if job['audio']:
            if job['portada'] and not core.music_cover(path):
                core.square_cover(path)
            core.validate_tags(path)
    status = 'Cancelada' if code is None else 'Completada' if code == 0 else 'Error'
    print(f'\nEstado: {status}' + (f' (código {code})' if code else ''))
    return status, files


class TerminalApp:
    def __init__(self):
        loaded = read_json(SETTINGS_PATH, {})
        self.settings = {**DEFAULTS, **{k: v for k, v in loaded.items()
                                        if k in DEFAULTS and isinstance(v, type(DEFAULTS[k]))}}
        self.history = read_json(HISTORY_PATH, [])
        self.queue = []

    def save(self, path, value):
        try:
            write_json(path, value)
        except OSError as error:
            print(f'No se pudo guardar {path.name}: {error}')

    def add_job(self, url, audio=True, args=None):
        if audio:
            parsed = urlparse(url)
            if (parsed.hostname in ('youtube.com', 'www.youtube.com', 'music.youtube.com', 'youtu.be')
                    and 'list' not in parse_qs(parsed.query)):
                url = core.find_music(url) or url
            args = audio_args(url, self.settings)
        return {'url': url, 'args': args, 'audio': audio, 'portada': self.settings['portada'], 'status': 'Pendiente'}

    def perform(self, job):
        try:
            status, files = execute(job)
        except OSError as error:
            print(f'No se pudo iniciar la descarga: {error}')
            status, files = 'Error', []
        job['status'] = status
        self.history.insert(0, {'fecha': datetime.now().isoformat(timespec='seconds'),
                                'estado': status, 'archivos': files, 'tipo': 'Audio' if job['audio'] else 'Video'})
        self.save(HISTORY_PATH, self.history)

    def new_download(self):
        heading('NUEVA DESCARGA')
        choice = core.choose('Elige una opción', {
            '1': 'Descargar música (MP3)', '2': 'Descargar video', '3': 'Consultar formatos',
            '4': 'Consultar información', '5': 'Opciones avanzadas', '0': 'Volver'})
        if choice == '0':
            return
        url = checked_url()
        if not url:
            return
        if choice in ('3', '4'):
            core.run(['--list-formats' if choice == '3' else '--dump-single-json', '--no-playlist', '--', url])
            return
        if choice == '1':
            job = self.add_job(url)
            print(f"\nDestino: {self.settings['destino']}\nFormato: MP3")
            print(f"Metadatos: {'Sí' if self.settings['metadatos'] else 'No'} | Portada: {'Sí' if self.settings['portada'] else 'No'}")
        elif choice == '2':
            job = self.add_job(url, audio=False, args=core.configure_download('2', url))
        else:
            job = self.add_job(url, audio=False, args=[*core.extra_args(), '--', url])
        action = core.choose('Elige una opción', {'1': 'Descargar ahora', '2': 'Añadir a la cola', '0': 'Cancelar'})
        if action == '1':
            self.perform(job)
        elif action == '2':
            self.queue.append(job)
            print('Añadida a la cola.')

    def queue_menu(self):
        while True:
            heading('COLA DE DESCARGAS')
            if not self.queue:
                print('La cola está vacía.')
            for index, job in enumerate(self.queue, 1):
                print(f"  {index}. {job['status']} — {job['url']}")
            choice = core.choose('Elige una opción', {'1': 'Añadir descarga', '2': 'Procesar pendientes',
                                 '3': 'Reintentar fallidas o canceladas', '0': 'Volver'})
            if choice == '0':
                return
            if choice == '1':
                self.new_download()
            if choice in ('2', '3'):
                for job in self.queue:
                    if job['status'] in (('Pendiente',) if choice == '2' else ('Error', 'Cancelada')):
                        self.perform(job)
                        if job['status'] == 'Cancelada':
                            break

    def history_menu(self):
        while True:
            heading('HISTORIAL')
            if not self.history:
                print('Todavía no hay descargas.')
                return
            for index, item in enumerate(self.history[:50], 1):
                label = Path(item['archivos'][0]).name if item.get('archivos') else item.get('tipo', 'Descarga')
                print(f"  {index}. {item.get('fecha', '')} | {item.get('estado', '')} | {label}")
            choice = core.ask('Número para ver detalles; 0 para volver', '0')
            if choice == '0':
                return
            if not choice.isdigit() or not 1 <= int(choice) <= min(50, len(self.history)):
                print('Opción no válida.')
                continue
            item = self.history[int(choice) - 1]
            files = item.get('archivos', [])
            for i, path in enumerate(files, 1):
                print(f'  {i}. {path}')
            if not files:
                print('No se registraron archivos.')
                continue
            selected = core.ask('Número de archivo; 0 para volver', '1')
            if not selected.isdigit() or not 1 <= int(selected) <= len(files):
                continue
            path = Path(files[int(selected) - 1])
            choice = core.choose('Elige una opción', {'1': 'Abrir archivo', '2': 'Abrir carpeta',
                                 '3': 'Corregir portada del MP3', '0': 'Volver'})
            if not path.is_file():
                print('El archivo ya no existe en la ruta registrada.')
            elif choice in ('1', '2'):
                try:
                    os.startfile(str(path if choice == '1' else path.parent))
                except (AttributeError, OSError) as error:
                    print(f'No se pudo abrir: {error}')
            elif choice == '3' and path.suffix.lower() == '.mp3':
                if not core.music_cover(str(path)):
                    print('Se conserva la portada actual.')
                core.validate_tags(str(path))

    def settings_menu(self):
        while True:
            heading('CONFIGURACIÓN')
            s = self.settings
            choice = core.choose('Elige una opción', {
                '1': f"Carpeta de destino: {s['destino']}", '2': f"Metadatos: {'Sí' if s['metadatos'] else 'No'}",
                '3': f"Portada: {'Sí' if s['portada'] else 'No'}", '4': f"Descargar lista completa: {'Sí' if s['lista'] else 'No'}",
                '5': f"Navegador para cookies: {s['navegador'] or 'Ninguno'}", '6': 'Comprobar dependencias', '0': 'Volver'})
            if choice == '0':
                return
            if choice == '1':
                folder = core.ask('Carpeta de destino (vacío para conservar)').strip('"')
                if folder:
                    s['destino'] = os.path.abspath(os.path.expanduser(folder))
            elif choice in ('2', '3', '4'):
                key = {'2': 'metadatos', '3': 'portada', '4': 'lista'}[choice]
                s[key] = not s[key]
            elif choice == '5':
                browser = core.ask('Navegador (chrome, edge, firefox; vacío para ninguno)').lower()
                if browser in ('', 'chrome', 'edge', 'firefox', 'brave', 'opera', 'vivaldi', 'chromium', 'safari', 'whale'):
                    s['navegador'] = browser
                else:
                    print('Navegador no reconocido; se conserva el valor anterior.')
            else:
                dependencies()
            self.save(SETTINGS_PATH, s)

    def tools_menu(self):
        heading('HERRAMIENTAS')
        choice = core.choose('Elige una opción', {'1': 'Corregir portada de un MP3', '2': 'Comprobar dependencias',
                             '3': 'Ver ayuda de yt-dlp', '0': 'Volver'})
        if choice == '1':
            path = core.ask('Ruta del MP3').strip('"')
            if path and Path(path).is_file() and Path(path).suffix.lower() == '.mp3':
                if not core.music_cover(path):
                    print('Se conserva la portada actual.')
                core.validate_tags(path)
            else:
                print('No se encontró el archivo MP3.')
        elif choice == '2':
            dependencies()
        elif choice == '3':
            core.run(['--help'])

    def main(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            print('Aviso: faltan ffmpeg o ffprobe en el PATH; consulta Herramientas > Comprobar dependencias.')
        try:
            import ytmusicapi  # noqa: F401
        except ImportError:
            print('Aviso: falta ytmusicapi para buscar portadas de álbum; consulta Herramientas.')
        while True:
            heading('YT-DLP DESCARGAS')
            pending = sum(job['status'] == 'Pendiente' for job in self.queue)
            choice = core.choose('Elige una opción', {'1': 'Nueva descarga', '2': f'Cola de descargas ({pending} pendientes)',
                                 '3': f'Historial ({len(self.history)} registros)', '4': 'Herramientas',
                                 '5': 'Configuración', '0': 'Salir'})
            if choice == '0':
                return
            {'1': self.new_download, '2': self.queue_menu, '3': self.history_menu,
             '4': self.tools_menu, '5': self.settings_menu}[choice]()


if __name__ == '__main__':
    try:
        TerminalApp().main()
    except (KeyboardInterrupt, EOFError):
        print('\nHasta luego. La cola pendiente no se guarda al salir.')
