# COMEÇAR AQUI

Este projeto já está preparado para gerar:

- Windows: `FioBenchmark-Setup-Windows-x64.exe`
- Linux: `FioBenchmark-Linux-x86_64.AppImage`

## 1. Subir ao GitHub

Crie um repositório vazio no GitHub.

No terminal:

```bash
git clone URL_DO_SEU_REPOSITORIO
cd NOME_DO_REPOSITORIO
git checkout -b main
```

Copie TODO o conteúdo desta pasta para dentro do repositório clonado.

Depois:

```bash
git add .
git commit -m "Versao inicial do FIO Benchmark"
git push -u origin main
```

## 2. Gerar os executáveis

No GitHub:

```text
Actions
→ Build installers
→ Run workflow
→ main
→ Run workflow
```

Espere os dois jobs terminarem.

Depois abra a execução e baixe os Artifacts:

- `FioBenchmark-Windows`
- `FioBenchmark-Linux`

O artifact Windows contém o `.exe`.
O artifact Linux contém o `.AppImage`.

## 3. Linux

Depois de baixar o AppImage:

```bash
chmod +x FioBenchmark-Linux-x86_64.AppImage
./FioBenchmark-Linux-x86_64.AppImage
```

O build Linux deste ZIP já usa o runtime novo do AppImage e não usa o runtime legado baseado em `libfuse.so.2`.

## 4. Arquivos importantes

- `app.py` — interface
- `benchmark_runner.py` — execução do benchmark
- `plot_runner.py` — geração dos gráficos
- `.github/workflows/build-installers.yml` — build automático
- `build/build_windows.ps1` — build Windows
- `build/build_linux.sh` — build Linux
- `build/windows_installer.iss` — instalador Windows
- `PACKAGING.md` — detalhes do empacotamento
