# FIO Benchmark — versão local simples

Esta versão faz apenas o fluxo local:

1. O usuário escolhe um gráfico no Tkinter.
2. Escolhe uma pasta que esteja no SSD, HD ou pendrive que deseja testar.
3. A aplicação cria uma pasta temporária exclusiva dentro dessa unidade.
4. `bench-fio` executa a sequência de benchmarks.
5. JSON e LOGs são salvos em `~/FioBenchmark/resultados/`.
6. `fio-plot` gera `grafico.png`.
7. O Tkinter exibe o PNG.
8. A pasta temporária usada para I/O é apagada ao final.

A aplicação nunca aponta o FIO diretamente para `/dev/sda`, `/dev/nvme0n1`
ou outro dispositivo bruto.

## Arquivos

- `app.py`: interface Tkinter.
- `benchmark_runner.py`: valida o alvo e executa `bench-fio`.
- `plot_runner.py`: encontra os dados produzidos e executa `fio-plot`.
- `requirements.txt`: dependências Python.

## Dependências para desenvolvimento

### Linux Debian/Ubuntu

O Tkinter e o FIO são dependências do sistema:

```bash
sudo apt update
sudo apt install fio python3-tk python3-venv
```

Crie o ambiente Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Execute:

```bash
python app.py
```

### Windows

Para esta fase de desenvolvimento:

1. Instale Python com suporte a Tkinter.
2. Instale uma versão do FIO para Windows e deixe `fio.exe` disponível no PATH.
3. Crie um ambiente virtual.
4. Execute:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

O `benchmark_runner.py` escolhe automaticamente `libaio` no Linux,
`windowsaio` no Windows e `posixaio` no macOS.

## Como escolher o SSD ou pendrive

Você não escolhe um dispositivo bruto.

Escolha uma pasta que esteja na unidade desejada.

Exemplos:

Linux, SSD do sistema:

```text
/home/seu_usuario
```

Linux, pendrive:

```text
/media/seu_usuario/NOME_DO_PENDRIVE
```

Windows, SSD C:

```text
C:\Users\SeuUsuario
```

Windows, pendrive E:

```text
E:\
```

A aplicação cria automaticamente uma pasta parecida com:

```text
.fio_benchmark_tmp_a1b2c3d4
```

e apaga somente essa pasta quando o benchmark termina.

## Tamanho por job

No `bench-fio`, quando o alvo é do tipo `directory`, o tamanho informado é
usado para um arquivo por job.

Por exemplo:

- tamanho: 1024 MB
- NumJobs: 4

A aplicação considera aproximadamente 4 GB de espaço necessário e ainda
exige uma pequena margem antes de iniciar.

## Modos com escrita

`write`, `randwrite` e `randrw` gravam dados no armazenamento.

O programa adiciona `--destructive` porque o `bench-fio` exige essa opção
para permitir testes de escrita, mas o alvo continua sendo somente a pasta
temporária exclusiva criada pela aplicação.

## Gráficos implementados

### 2D — IOPS e Latência por IODepth

Usa:

```text
fio-plot -l
```

### 3D — IOPS × IODepth × NumJobs

Usa:

```text
fio-plot -L -t iops
```

### Line Chart — LOG do FIO

Usa:

```text
fio-plot -g -t iops
fio-plot -g -t lat
fio-plot -g -t iops lat
```

conforme a métrica selecionada.

### 2D agrupado — IOPS e Latência

Usa:

```text
fio-plot -l --group-bars
```

### 3D — Latência × IODepth × NumJobs

Usa:

```text
fio-plot -L -t lat
```

## Observação sobre a versão final

Esta pasta é a versão de desenvolvimento.

A versão final ainda deverá empacotar automaticamente FIO, Python,
fio-plot e todas as dependências para que o usuário final não precise
instalar nada nem usar terminal.


## Aplicativo instalável

Consulte `PACKAGING.md`.

O GitHub Actions gera automaticamente:

- `FioBenchmark-Setup-Windows-x64.exe`
- `FioBenchmark-Linux-x86_64.AppImage`

O usuário final não precisa instalar Python, pip, fio-plot, bench-fio ou FIO.
