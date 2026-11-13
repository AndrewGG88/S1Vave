# Guía de Instalación de S1Vave (Plugin DAW)

S1Vave funciona de forma nativa en tu DAW mediante el plugin anfitrión gratuito VIBE FM (formatos VST3, CLAP y AU).

---

## Paso 1: Instalar el Plugin Anfitrión Gratuito VIBE FM

Descarga e instala la versión oficial para tu sistema operativo desarrollada por Sven Trogus (zvenson):

* **Windows (10 / 11)**: [Descargar instalador de Windows (.exe)](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Windows-Setup.exe)
* **macOS (11+, Apple Silicon e Intel)**: [Descargar paquete de macOS (.pkg)](https://thefirmwarehub.com/fw/vibe/VIBE-FM-0.7.9-macOS.pkg)
* **Linux (Ubuntu / Debian x86_64)**: [Descargar paquete .deb](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst_0.7.9-1_amd64.deb)
* **Linux (Fedora x86_64)**: [Descargar paquete .rpm](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst-0.7.9-1.x86_64.rpm)
* **Linux (Cualquier distribución)**: [Descargar .tar.gz con install.sh](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Linux.tar.gz)
* **Raspberry Pi / ARM64 (Debian / Pi OS)**: [Descargar .deb ARM64](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst_0.7.9-1_arm64.deb)
* **Raspberry Pi / ARM64 (Fedora)**: [Descargar .rpm ARM64](https://thefirmwarehub.com/fw/vibe/vibe-fm-vst-0.7.9-1.aarch64.rpm)
* **Raspberry Pi / ARM64 (Genérico)**: [Descargar .tar.gz ARM64](https://thefirmwarehub.com/fw/vibe/VIBE-FM-VST-0.7.9-Linux-arm64.tar.gz)

---

## Paso 2: Instalar S1Vave

### Opción A: Windows (Instalador Automático)
Ejecuta `S1Vave-v2.0-Windows-Setup.exe`.
Copia automáticamente el motor de audio, metadatos, icono e interfaz web en las carpetas de VIBE FM:
* Carpeta de usuario: `%APPDATA%\VIBE FM\Firmware`
* Carpeta de sistema: `C:\ProgramData\VIBE FM\Firmware`

### Opción B: macOS, Linux y Windows (Arrastrar y Soltar)
1. Abre tu DAW preferido (FL Studio, Ableton Live, Reaper, Bitwig, Cubase, Logic Pro).
2. Inserta **VIBE FM VST** (o AU / CLAP) en una pista MIDI.
3. Arrastra el archivo descargado `s1vave.zip` directamente sobre la ventana del plugin VIBE FM (sin descomprimir).
4. S1Vave se descomprime, se instala y comienza a sonar al instante.

### Opción C: Copia Manual de Archivos
Descomprime `s1vave.zip` y coloca los archivos `s1vave.wasm`, `s1vave.json`, `s1vave.png` y la carpeta `s1vave.editor` en:
* **macOS**: `~/Library/Application Support/VIBE FM/Firmware` (En Finder: Ir -> Ir a la carpeta...)
* **Windows**: `%APPDATA%\VIBE FM\Firmware`
* **Linux**: `~/.local/share/VIBE FM/Firmware`

---

## Paso 3: Tocar y Automatizar

1. Selecciona **S1VAVE** en el menú desplegable superior del plugin.
2. Se abrirá la interfaz gráfica dedicada con todos los controles del sintetizador.
3. Todos los parámetros quedan expuestos a tu DAW para grabar automatizaciones y mapear controladores MIDI.

---

## Solución de Problemas (Pantalla en Blanco en Ableton Live 12 / Windows)

Si la ventana del plugin VIBE FM se abre totalmente en blanco en Ableton Live 12 u otro DAW en Windows:
1. Instala o repara **Microsoft Edge WebView2 Runtime** (Evergreen Bootstrapper) y reinicia tu DAW.
2. Haz clic derecho sobre el plugin en el navegador de Ableton para activar o desactivar **Auto-Scale Plugin Window** (escalado HiDPI), o define la variable de entorno `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--disable-gpu` si hay conflicto con tu controlador gráfico.

---

## Créditos y Licencias

* Sintetizador S1Vave: Andrew GG (GNU General Public License v3.0)
* Plugin VIBE FM y OberVave: Sven Trogus (zvenson, https://thefirmwarehub.com/vibe/)

