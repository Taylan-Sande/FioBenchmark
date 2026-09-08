#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "== FIO Benchmark: build Linux AppImage =="

python3 -m pip install --upgrade pip
python3 -m pip install -r build/requirements-build.txt

rm -rf \
  build/fio-src \
  build/AppDir \
  build/linux-selftest.txt \
  build/linux-appimage-selftest.txt \
  dist/FioBenchmark \
  release

mkdir -p \
  build/AppDir/usr/lib/FioBenchmark \
  build/AppDir/usr/bin \
  build/AppDir/usr/share/applications \
  build/AppDir/usr/share/icons/hicolor/256x256/apps \
  release

echo "== Compilando FIO 3.42 =="
git clone --depth 1 --branch fio-3.42 https://github.com/axboe/fio.git build/fio-src

pushd build/fio-src >/dev/null
./configure
make -j"$(nproc)"
cp fio "$PROJECT_ROOT/build/AppDir/usr/bin/fio"
popd >/dev/null

chmod +x build/AppDir/usr/bin/fio
build/AppDir/usr/bin/fio --version

echo "== Gerando aplicação PyInstaller =="
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
draw.rounded_rectangle(
    (28, 28, 228, 228),
    radius=36,
    outline=(230, 230, 230, 255),
    width=10,
)
draw.rectangle((62, 74, 194, 96), fill=(230, 230, 230, 255))
draw.rectangle((62, 117, 165, 139), fill=(230, 230, 230, 255))
draw.rectangle((62, 160, 136, 182), fill=(230, 230, 230, 255))
img.save(
    "build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png"
)
PY

write_apprun() {
cat > build/AppDir/AppRun <<'EOF'
#!/bin/sh
APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")}"

export PATH="$APPDIR/usr/bin:$PATH"
export FIO_BENCHMARK_FIO="$APPDIR/usr/bin/fio"
export MPLBACKEND=Agg
export LD_LIBRARY_PATH="$APPDIR/usr/lib:$APPDIR/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

exec "$APPDIR/usr/lib/FioBenchmark/FioBenchmark" "$@"
EOF
chmod +x build/AppDir/AppRun
}

write_apprun

cp \
  build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png \
  build/AppDir/fiobenchmark.png

ln -sf \
  usr/share/icons/hicolor/256x256/apps/fiobenchmark.png \
  build/AppDir/.DirIcon

echo "== Testando o bundle antes do AppImage =="
APPDIR="$PROJECT_ROOT/build/AppDir" \
FIO_BENCHMARK_FIO="$PROJECT_ROOT/build/AppDir/usr/bin/fio" \
PATH="$PROJECT_ROOT/build/AppDir/usr/bin:$PATH" \
MPLBACKEND=Agg \
xvfb-run -a \
  build/AppDir/usr/lib/FioBenchmark/FioBenchmark \
  --self-test "$PROJECT_ROOT/build/linux-selftest.txt"

cat build/linux-selftest.txt
grep -q "RESULTADO: OK" build/linux-selftest.txt

LINUXDEPLOY="build/linuxdeploy-x86_64.AppImage"
APPIMAGETOOL="build/appimagetool-x86_64.AppImage"
APPIMAGE_RUNTIME="build/runtime-x86_64"

curl -fL \
  "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage" \
  -o "$LINUXDEPLOY"

curl -fL \
  "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
  -o "$APPIMAGETOOL"

curl -fL \
  "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64" \
  -o "$APPIMAGE_RUNTIME"

chmod +x "$LINUXDEPLOY" "$APPIMAGETOOL" "$APPIMAGE_RUNTIME"

export APPIMAGE_EXTRACT_AND_RUN=1

echo "== Coletando bibliotecas Linux =="
"$LINUXDEPLOY" \
  --appdir build/AppDir \
  --executable build/AppDir/usr/bin/fio \
  --executable build/AppDir/usr/lib/FioBenchmark/FioBenchmark \
  --desktop-file build/AppDir/usr/share/applications/fiobenchmark.desktop \
  --icon-file build/AppDir/usr/share/icons/hicolor/256x256/apps/fiobenchmark.png

write_apprun

echo "== Criando AppImage =="
ARCH=x86_64 "$APPIMAGETOOL" \
  --runtime-file "$APPIMAGE_RUNTIME" \
  --no-appstream \
  build/AppDir \
  release/FioBenchmark-Linux-x86_64.AppImage

chmod +x release/FioBenchmark-Linux-x86_64.AppImage

echo "== Testando o AppImage final =="
APPIMAGE_EXTRACT_AND_RUN=1 \
xvfb-run -a \
  release/FioBenchmark-Linux-x86_64.AppImage \
  --self-test "$PROJECT_ROOT/build/linux-appimage-selftest.txt"

cat build/linux-appimage-selftest.txt
grep -q "RESULTADO: OK" build/linux-appimage-selftest.txt

echo
echo "Concluído."
echo "AppImage em: release/FioBenchmark-Linux-x86_64.AppImage"
