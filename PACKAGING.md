# Empacotamento do FIO Benchmark

## Objetivo

O usuário final não precisa instalar Python, pip, fio-plot, bench-fio ou FIO.

São gerados dois pacotes separados:

- Windows: `FioBenchmark-Setup-Windows-x64.exe`
- Linux: `FioBenchmark-Linux-x86_64.AppImage`

Isso é necessário porque o PyInstaller gera binários para o sistema operacional
em que o build é executado.

## Build automático pelo GitHub

O arquivo:

```text
.github/workflows/build-installers.yml
```

cria os dois pacotes usando máquinas Windows e Linux do GitHub.

### Rodar manualmente

No GitHub:

```text
Actions
→ Build installers
→ Run workflow
```

Ao terminar, baixe os dois arquivos em `Artifacts`.

### Rodar ao criar uma versão

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Windows

O build baixa o MSI x64 oficial do FIO 3.42, extrai o FIO para dentro do
aplicativo, empacota Python e as bibliotecas com PyInstaller e cria um
instalador com Inno Setup.

O usuário final executa somente:

```text
FioBenchmark-Setup-Windows-x64.exe
```

## Linux

O build compila o FIO 3.42, empacota a aplicação Python e monta um AppImage
com linuxdeploy/AppImageKit.

O usuário final recebe:

```text
FioBenchmark-Linux-x86_64.AppImage
```

O AppImage não exige instalação de Python, FIO ou fio-plot. Dependendo do
navegador e do desktop Linux, pode ser necessário marcar o arquivo como
executável antes do primeiro uso; isso é uma regra de segurança do Linux,
não uma instalação de dependências.

## Como o código encontra as dependências

`runtime_tools.py` procura o FIO nesta ordem:

1. FIO definido internamente pelo pacote;
2. FIO dentro do AppImage;
3. FIO dentro do bundle Windows;
4. FIO disponível no PATH, apenas como fallback para desenvolvimento.

`bench_fio` e `fio_plot` são importados diretamente do pacote Python
`fio-plot`, em vez de depender dos comandos que o pip instalaria no PATH.

## Desenvolvimento

Para continuar testando pelo código-fonte:

```bash
pip install -r requirements.txt
python app.py
```

Nesse modo ainda é necessário ter FIO instalado no sistema.


## Correção de compatibilidade AppImage/FUSE

O build Linux usa o `appimagetool` atual de `AppImage/appimagetool` e injeta
explicitamente o runtime Type 2 atual de `AppImage/type2-runtime`.

Isso evita o runtime legado que tentava carregar `libfuse.so.2` dinamicamente.
O runtime atual é estaticamente ligado e não requer `libfuse2` instalada no
computador do usuário.
