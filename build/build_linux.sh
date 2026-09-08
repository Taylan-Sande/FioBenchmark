#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "== FIO Benchmark: build Linux AppImage =="

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install "PyInstaller==6.22.2"

rm -rf build/fio-src build/AppDir dist/FioBenchmark release
mkdir -p build/AppDir/usr/lib/FioBenchmark
mkdir -p build/AppDir/usr/bin
mkdir -p build/AppDir/usr/share/applications
mkdir -p build/AppDir/usr/share/icons/hicolor/256x256/apps
mkdir -p release

git clone --depth 1 --branch fio-3.42 https://github.com/axboe/fio.git build/fio-src
pushd build/fio-src >/dev/null
./configure
make -j"$(nproc)"
cp fio "$PROJECT_ROOT/build/AppDir/usr/bin/fio"
popd >/dev/null

python3 -m PyInstaller build/fio_benchmark.spec --noconfirm --clean
cp -a dist/FioBenchmark/. build/AppDir/usr/lib/FioBenchmark/

cat > build/AppDir/usr/share/applications/fiobenchmark.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=FIO Benchmark
Exec=FioBenchmark
Icon=fiobenchmark
Categories=Utility;
Terminal=false
EOF

python3 - <<'PY'
from PIL import Image, ImageDraw

img = Image.new("RGBA", (256, 256), (30, 30, 30, 255))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle((28, 28, 228, 228), radius=36, outline=(230, 230, 230, 255), width=10)
draw.rectangle((62, 74, 194, 96), fill=(230, 230, 230, 255))
draw.rectangle((62, 117, 165, 139), fill=(230, 230, 230, 255))
draw.rectangle((62, 160, 136, 182), fill=(230, 230, 230, 255))
img.save("build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png")
PY

cat > build/AppDir/AppRun <<'EOF'
#!/bin/sh
APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")}"
export PATH="$APPDIR/usr/bin:$PATH"
export FIO_BENCHMARK_FIO="$APPDIR/usr/bin/fio"
export MPLBACKEND=Agg
exec "$APPDIR/usr/lib/FioBenchmark/FioBenchmark" "$@"
EOF
chmod +x build/AppDir/AppRun
chmod +x build/AppDir/usr/bin/fio

cp build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png build/AppDir/fiobenchmark.png
ln -sf usr/share/icons/hicolor/256x256/apps/fiobenchmark.png build/AppDir/.DirIcon

LINUXDEPLOY="build/linuxdeploy-x86_64.AppImage"
APPIMAGETOOL="build/appimagetool-x86_64.AppImage"
APPIMAGE_RUNTIME="build/runtime-x86_64"

curl -fL \
  "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage" \
  -o "$LINUXDEPLOY"

# Usa o appimagetool mantido atualmente pelo projeto AppImage.
curl -fL \
  "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
  -o "$APPIMAGETOOL"

# Runtime Type 2 atual. Ele é estaticamente ligado e não exige libfuse2
# instalada no computador do usuário.
curl -fL \
  "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64" \
  -o "$APPIMAGE_RUNTIME"

chmod +x "$LINUXDEPLOY" "$APPIMAGETOOL" "$APPIMAGE_RUNTIME"

# Necessário no runner do GitHub, onde FUSE pode não estar disponível.
export APPIMAGE_EXTRACT_AND_RUN=1

"$LINUXDEPLOY" \
  --appdir build/AppDir \
  --executable build/AppDir/usr/bin/fio \
  --desktop-file build/AppDir/usr/share/applications/fiobenchmark.desktop \
  --icon-file build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png

cat > build/AppDir/AppRun <<'EOF'
#!/bin/sh
APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")}"
export PATH="$APPDIR/usr/bin:$PATH"
export FIO_BENCHMARK_FIO="$APPDIR/usr/bin/fio"
export MPLBACKEND=Agg
exec "$APPDIR/usr/lib/FioBenchmark/FioBenchmark" "$@"
EOF
chmod +x build/AppDir/AppRun

ARCH=x86_64 "$APPIMAGETOOL" \
  --runtime-file "$APPIMAGE_RUNTIME" \
  --no-appstream \
  build/AppDir \
  release/FioBenchmark-Linux-x86_64.AppImage

chmod +x release/FioBenchmark-Linux-x86_64.AppImage

echo
echo "Concluído."
echo "AppImage em: release/FioBenchmark-Linux-x86_64.AppImage"
