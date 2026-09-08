import builtins
import contextlib
import sys
import tempfile


def run_embedded_cli(program_name, main_function, arguments):
    old_argv = sys.argv[:]

    had_exit = hasattr(builtins, "exit")
    had_quit = hasattr(builtins, "quit")

    old_exit = getattr(builtins, "exit", None)
    old_quit = getattr(builtins, "quit", None)

    builtins.exit = sys.exit
    builtins.quit = sys.exit

    with tempfile.TemporaryFile(
        mode="w+",
        encoding="utf-8",
        errors="replace",
    ) as output:
        try:
            sys.argv = [program_name, *arguments]

            try:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = main_function()

                if result is None:
                    return_code = 0
                elif isinstance(result, int):
                    return_code = result
                else:
                    return_code = 0

            except SystemExit as exc:
                if exc.code is None:
                    return_code = 0
                elif isinstance(exc.code, int):
                    return_code = exc.code
                else:
                    return_code = 1

            output.flush()
            output.seek(0)
            text = output.read()

            return return_code, text

        finally:
            sys.argv = old_argv

            if had_exit:
                builtins.exit = old_exit
            else:
                delattr(builtins, "exit")

            if had_quit:
                builtins.quit = old_quit
            else:
                delattr(builtins, "quit")
