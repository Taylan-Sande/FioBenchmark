# FIO Benchmark

Interface gráfica para rodar benchmarks de armazenamento com **FIO** e gerar gráficos com **fio-plot**.

Funciona no **Windows** (instalador `.exe`) e no **Linux** (AppImage). O fluxo recomendado de distribuição é o **GitHub Actions → Build installers**, baixando o artifact gerado.

---

## Índice

1. [O que este app faz](#o-que-este-app-faz)
2. [Instalação (usuário final)](#instalação-usuário-final)
3. [Como usar](#como-usar)
4. [Tipos de gráfico](#tipos-de-gráfico)
5. [Parâmetros importantes](#parâmetros-importantes)
6. [Presets e estimativa de tempo](#presets-e-estimativa-de-tempo)
7. [Onde os resultados são salvos](#onde-os-resultados-são-salvos)
8. [Relatório HTML e comparação](#relatório-html-e-comparação)
9. [Dark mode e preferências](#dark-mode-e-preferências)
10. [Cancelar um teste](#cancelar-um-teste)
11. [Gerar o instalador (GitHub Actions)](#gerar-o-instalador-github-actions)
12. [Desenvolvimento local](#desenvolvimento-local)
13. [Arquivos do projeto](#arquivos-do-projeto)
14. [Solução de problemas](#solução-de-problemas)

---

## O que este app faz

1. Você escolhe uma **pasta na unidade** que deseja testar (SSD, HD, pendrive, etc.).
2. O app cria uma pasta temporária **só dele** nessa unidade, roda o FIO e **apaga** a pasta temp ao terminar.
3. Os resultados (JSON, LOG e gráficos PNG) vão para a **pasta de resultados** que você configurar.
4. Opcionalmente gera **um** ou **todos** os tipos de gráfico do fio-plot.

> O teste com modos de **escrita** (`write`, `randwrite`, `randrw`) grava dados na unidade. O app avisa antes e usa só a pasta temporária exclusiva.

---

## Instalação (usuário final)

### Windows

1. No GitHub do projeto: **Actions → Build installers →** abra a execução mais recente (ou rode o workflow).
2. Baixe o artifact **`FioBenchmark-Windows`**.
3. Extraia e execute `FioBenchmark-Setup-Windows-x64.exe`.
4. Abra o atalho **FIO Benchmark**.

### Linux

1. Baixe o artifact **`FioBenchmark-Linux`**.
2. Torne o AppImage executável e rode:

```bash
chmod +x FioBenchmark-Linux-x86_64.AppImage
./FioBenchmark-Linux-x86_64.AppImage
```

O build Linux usa runtime moderno de AppImage (não depende de `libfuse.so.2` legado).

---

## Como usar

1. **Gráfico** — escolha o tipo (ou marque *Gerar todos os gráficos*).
2. **Armazenamento a testar** — *Escolher...* uma pasta **existente** na unidade alvo.
3. **Pasta de resultados** — onde salvar a sessão (padrão: `~/FioBenchmark/resultados`).
4. **Configurações comuns** — modo de I/O, block size, runtime, ramp, título.
5. **Sequência de testes** — IODepth(s), NumJobs (e opções de LOG no Line Chart).
6. Clique em **Executar benchmark e gerar gráfico**.

Atalhos:

| Tecla | Ação |
|-------|------|
| `F11` | Alternar tela cheia |
| `Esc` | Sair da tela cheia |

---

## Tipos de gráfico

| Nome na interface | O que mostra | Observação |
|-------------------|--------------|------------|
| **2D — IOPS e Latência por IODepth** | Barras de IOPS/latência variando a profundidade de fila | NumJobs fixo |
| **3D — IOPS × IODepth × NumJobs** | Superfície/barras 3D de IOPS | Precisa de **lista** de NumJobs |
| **Line Chart — dados de LOG do FIO** | IOPS e/ou latência **ao longo do tempo** | Precisa dos arquivos `.log` |
| **2D agrupado — IOPS e Latência** | Como o 2D, com barras agrupadas | NumJobs fixo |
| **3D — Latência × IODepth × NumJobs** | 3D de latência | Lista de NumJobs |

### Gerar todos

Com a opção marcada, o app:

- roda **um** conjunto de testes com a **lista completa** de NumJobs e IODepths;
- gera os **5** PNGs na mesma pasta de sessão;
- gráficos 2D/Line usam o **primeiro** NumJobs da lista.

Se um gráfico falhar (ex.: Line Chart sem `.log`), os outros ainda são gerados e um arquivo `avisos_graficos.txt` pode aparecer na sessão.

---

## Parâmetros importantes

| Parâmetro | Significado |
|-----------|-------------|
| **Modo** | `randread` / `randwrite` / `randrw` / `read` / `write` |
| **Block size** | Tamanho de cada I/O (`4k`, `128k`, `1m`, …) |
| **Tamanho por job (MB)** | Tamanho do arquivo de teste **por** job; com NumJobs=4 e 1024 MB ≈ ~4 GB na unidade |
| **Runtime (s)** | Duração de cada combinação IODepth×NumJobs |
| **Ramp time (s)** | Aquecimento antes de medir (não entra na média final do FIO da mesma forma) |
| **IODepth** | Quantos I/Os podem ficar pendentes (fila) |
| **NumJobs** | Quantos processos/threads FIO em paralelo |
| **Intervalo do LOG (ms)** | Resolução dos `.log` (Line Chart); `1000` = 1 amostra/s |

---

## Presets e estimativa de tempo

- **Teste rápido** — runtime 10 s, ramp 2 s, poucos IODepth/NumJobs (bom para validar a unidade).
- **Completo** — runtime 30 s, sequência maior de IODepth/NumJobs.

Abaixo dos presets aparece uma **estimativa** aproximada:

```text
Estimativa: ~X min YY s  ·  N job(s) FIO + M gráfico(s)
```

É uma previsão grosseira (`(runtime + ramp + overhead) × jobs` + tempo de plot). O tempo real depende do disco e do sistema.

---

## Onde os resultados são salvos

### Pasta base

Padrão: `~/FioBenchmark/resultados`  
(Windows: `C:\Users\<você>\FioBenchmark\resultados`)

Você pode mudar em **3. Pasta de resultados**.

### Pasta de cada sessão

Nome no formato:

```text
<tipo>_<YYYYMMDD_HHMMSS>
```

Exemplos:

- `2d_iops_lat_20260908_143015`
- `3d_iops_20260908_150000`
- `todos_20260908_151200` (quando gera todos os gráficos)

### Conteúdo típico da sessão

| Arquivo | Descrição |
|---------|-----------|
| `*.json` | Saída do FIO por combinação de teste |
| `*.log` | Séries temporais (IOPS/latência/bw) — usados no Line Chart |
| `grafico_*.png` | Imagens geradas pelo fio-plot |
| `relatorio.html` | Se você exportar o relatório |
| `avisos_graficos.txt` | Se algum gráfico falhou no modo “todos” |

Preferências da interface (última pasta de teste, pasta de resultados, dark mode) ficam em:

```text
~/FioBenchmark/config.json
```

---

## Relatório HTML e comparação

- **Exportar relatório HTML** — gera uma página com parâmetros + imagens embutidas (pode abrir no navegador e arquivar).
- **Comparar duas pastas** — escolhe duas sessões e visualiza os PNGs lado a lado.

---

## Dark mode e preferências

Botão **🌙 Modo escuro / ☀ Modo claro** no canto superior direito. A escolha é lembrada na próxima abertura.

---

## Cancelar um teste

Durante a execução, use **Parar**:

- sinaliza cancelamento entre jobs;
- tenta encerrar o processo `fio` em andamento;
- limpa a pasta temporária na unidade testada.

O job que já está no meio do *runtime* pode levar alguns segundos para parar.

---

## Gerar o instalador (GitHub Actions)

**Sim — esse é o caminho certo e está alinhado com o projeto.**

### Fluxo

1. Faça push do código (incluindo os `.py` novos) para o repositório.
2. No GitHub:

```text
Actions → Build installers → Run workflow
```

(ou faça push de uma tag `v*`, se quiser disparar por tag).

3. Espere os jobs **Windows installer** e **Linux AppImage** terminarem.
4. Baixe os artifacts:

- `FioBenchmark-Windows` → setup `.exe`
- `FioBenchmark-Linux` → `.AppImage`

### Por que funciona com os módulos novos?

O PyInstaller parte de `app.py` e segue os `import`. Além disso, o `build/fio_benchmark.spec` lista explicitamente:

- `user_settings`
- `report_utils`
- `bench_compat`
- `benchmark_runner`
- `plot_runner`
- etc.

Ou seja: **depois de commitar e rodar o Actions de novo**, o executável/AppImage já deve incluir as features novas.

### Checklist antes de publicar uma build

- [ ] Todos os `.py` commitados e no branch que o workflow usa  
- [ ] Workflow **Build installers** verde  
- [ ] Self-test dos artifacts (os scripts de build já geram arquivos `*-selftest.txt`)  
- [ ] Teste manual rápido no Windows e/ou Linux  

Detalhes extras de empacotamento: ver `PACKAGING.md` e `COMEÇAR_AQUI.md`.

---

## Desenvolvimento local

```bash
git clone <url-do-repo>
cd FioBenchmark
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

# FIO precisa estar instalado no sistema (ou virá no pacote final)
python app.py
```

Self-test:

```bash
python app.py --self-test
```

---

## Arquivos do projeto

| Arquivo | Função |
|---------|--------|
| `app.py` | Interface Tkinter |
| `benchmark_runner.py` | Orquestra o bench-fio e a pasta de sessão |
| `plot_runner.py` | Gera um ou todos os gráficos |
| `bench_compat.py` | Compatibilidade Windows + progresso/cancelamento |
| `user_settings.py` | Preferências em `~/FioBenchmark/config.json` |
| `report_utils.py` | Exportação HTML |
| `embedded_cli.py` | Executa bench-fio/fio-plot embutidos |
| `runtime_tools.py` / `runtime_selftest.py` | Runtime e testes |
| `build/` | Scripts PyInstaller, Inno Setup, AppImage |
| `.github/workflows/build-installers.yml` | CI que gera os instaladores |

---

## Solução de problemas

### “Line Chart precisa dos arquivos .log”

O Line Chart depende de `write_iops_log` / `write_lat_log`. Rode de novo com a build atualizada; na pasta da sessão devem aparecer arquivos `*.log` junto dos `*.json`. Se a mensagem de erro listar os arquivos da sessão, use isso para diagnosticar.

### Pouco espaço na unidade

O app estima espaço com margem (~10%) com base em *tamanho por job × max NumJobs*. Reduza o tamanho ou o número de jobs.

### Benchmark cancelado / Parar

Normal se você clicou em **Parar**. A pasta temp é removida; a pasta de resultados pode ficar parcial.

### AppImage não abre

```bash
chmod +x FioBenchmark-Linux-x86_64.AppImage
./FioBenchmark-Linux-x86_64.AppImage
```

### Erros da interface

Detalhes podem ser gravados em:

```text
~/FioBenchmark/erro_interface.log
```

---

## Licenças de terceiros

FIO, fio-plot e demais dependências têm licenças próprias. Veja `THIRD_PARTY_NOTICES.md`.

---

**FIO Benchmark** — medir armazenamento com FIO, visualizar com fio-plot, sem linha de comando.

