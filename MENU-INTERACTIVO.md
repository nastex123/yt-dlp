# Menú interactivo

En Windows, abre `iniciar-menu.cmd` con doble clic o ejecuta desde PowerShell:

```powershell
python menu_yt_dlp.py
```

El menú permite descargar audio o video, elegir la calidad del video, consultar formatos y pasar opciones adicionales de yt-dlp. Para salir, selecciona `0` o pulsa Ctrl+C. Para volver al menú sin ejecutar una descarga, deja el enlace vacío.

Al descargar audio, el menú usa MP3, incrusta metadatos y portada, y no guarda un archivo JSON. Si el enlace pertenece a una lista o álbum, descarga la colección completa en una carpeta con su título. Para un video individual de YouTube, busca una canción en YouTube Music y selecciona el primer resultado si coinciden el título, el artista y la duración. Si no hay una coincidencia clara, ofrece hasta diez resultados para elegir o permite conservar el enlace original. Los enlaces con listas no se sustituyen automáticamente.

El nombre de descarga usa el título sin el identificador del video. Al terminar una descarga de audio, el menú usa ffprobe para mostrar las etiquetas y la portada que quedaron guardadas; los campos ausentes se indican como no disponibles. Dos canciones con el mismo título pueden compartir nombre de archivo: selecciona carpetas distintas para conservar ambas.

Para obtener la portada del álbum, instala `ytmusicapi` con `python -m pip install ytmusicapi`. El menú busca la canción en YouTube Music y solo usa su portada si coincide el identificador del video. Si no encuentra una coincidencia, conserva la miniatura de yt-dlp y la recorta al centro si es rectangular; esa miniatura puede ser distinta de la portada del álbum. La opción 7 permite corregir un MP3 anterior que conserve su enlace de YouTube en los metadatos. El audio no se vuelve a codificar.

Necesitas Python 3.11 o posterior. FFmpeg y ffprobe deben estar disponibles en el PATH para convertir audio, combinar formatos y realizar otras tareas de posprocesamiento. Para el soporte completo de YouTube, consulta las dependencias recomendadas en el README, incluidas yt-dlp-ejs y un entorno JavaScript compatible.

Las opciones avanzadas se introducen como argumentos individuales: por ejemplo, `--limit-rate` en una línea y `2M` en la siguiente. Puedes consultar todas las opciones con la entrada de ayuda del menú. Se respetan los archivos de configuración de yt-dlp habituales. La carpeta predeterminada es la carpeta del proyecto.
