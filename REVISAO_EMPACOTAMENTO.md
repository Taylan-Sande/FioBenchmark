# Revisão do empacotamento

Esta versão do projeto não depende de o usuário instalar Python, pip, fio-plot,
bench-fio, Pillow, NumPy, Matplotlib ou FIO.

## O que foi reforçado

1. Pillow é coletado explicitamente no spec do PyInstaller.
2. Imports dinâmicos usados por Tkinter, Matplotlib e gráficos 3D são explícitos.
3. Matplotlib usa o backend Agg para geração dos PNGs.
4. A interface não depende mais de `PIL.ImageTk` para mostrar o PNG; o Pillow
   redimensiona e o próprio `tk.PhotoImage` exibe a imagem.
5. Erros de callbacks do Tkinter são gravados em
   `~/FioBenchmark/erro_interface.log`.
6. No Linux, linuxdeploy inspeciona tanto o FIO quanto o executável principal.
7. O AppRun inclui `usr/lib` no `LD_LIBRARY_PATH`.
8. O build Linux testa o bundle antes do AppImage e testa o AppImage final.
9. O build Windows testa o bundle, gera o instalador, instala silenciosamente
   numa pasta temporária e testa a aplicação já instalada.
10. Os relatórios de self-test são enviados junto com os artifacts.

A ideia é simples: se faltar uma dependência, o GitHub Actions deve falhar
antes de publicar um pacote aparentemente válido.
