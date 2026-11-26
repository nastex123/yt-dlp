# Menú interactivo

En Windows, abre `iniciar-menu.cmd` con doble clic o ejecuta desde PowerShell:

```powershell
python terminal_app.py
```

Instala Python 3.11 o posterior y las dependencias recomendadas desde la carpeta del proyecto:

```powershell
python -m pip install -e ".[default,terminal]"
```

FFmpeg y ffprobe deben estar en el PATH. Para soporte completo de YouTube consulta las dependencias recomendadas del README, incluidos yt-dlp-ejs y un entorno de JavaScript compatible. En **Herramientas > Comprobar dependencias** puedes revisar el entorno.

El menú ofrece descargas de música y video, consulta de formatos e información, opciones avanzadas, una cola secuencial, historial, herramientas y ajustes. Los ajustes y el historial se guardan en `%LOCALAPPDATA%\yt-dlp-menu`; la cola solo existe durante la sesión y no guarda enlaces ni opciones al cerrar. La carpeta predeterminada de descarga es la carpeta del proyecto, y puede cambiarse en Configuración.

En música se usa MP3. Por defecto se incrustan metadatos y portada, y se descarga la lista o álbum completo en una carpeta con su título. Esas opciones pueden cambiarse en Configuración. Los enlaces individuales de YouTube se buscan en YouTube Music y se selecciona la primera canción solo si coinciden el título, artista y duración; de lo contrario se ofrece elegir o conservar el enlace original. No se guarda JSON de metadatos. Dos canciones con el mismo título en una carpeta pueden coincidir en el nombre de archivo.

Para la portada se busca el identificador exacto de la canción en YouTube Music. Si no se encuentra, se conserva la miniatura de yt-dlp y se recorta al centro cuando es rectangular; puede ser diferente de la portada del álbum. El audio no se vuelve a codificar durante este proceso. Herramientas y el historial permiten corregir la portada de un MP3 existente que conserve su enlace de YouTube en los metadatos.

Durante una descarga, yt-dlp muestra el progreso directamente. Pulsa Ctrl+C para cancelarla y volver al menú; pueden quedar archivos parciales. La cola procesa un elemento a la vez y permite reintentar fallos o cancelaciones. El historial permite abrir los archivos y sus carpetas, pero no los elimina. Las opciones avanzadas se introducen como argumentos individuales: por ejemplo, `--limit-rate` en una línea y `2M` en la siguiente. Se respetan los archivos de configuración habituales de yt-dlp.
