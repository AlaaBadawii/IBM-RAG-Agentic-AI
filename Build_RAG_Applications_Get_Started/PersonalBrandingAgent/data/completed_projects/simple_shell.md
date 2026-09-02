# simple_shell — custom Unix shell written in C

## Status
Completed (team project: Alaa Badawii + Farouk Bin Lhwaty).
Remote origin: `FaroukBinLhouita/simple_shell` (AUTHORS file lists both).

## What this is
A from-scratch command-line interpreter in C, a low-level systems milestone in
the ALX program. It reads user input, tokenizes it, resolves commands against
`PATH`, and runs them.

## Evidence of actual implementation
`/home/alaabadawii/ALX/simple_shell/`
- `shell.h` — header with the full API (own `_getline`, `_strtok`, `_strdup`,
  `get_path`, `exe_cmd`, `exe_env`, memory-free helpers).
- `mymain.c` — main loop: prompt -> read line -> tokenize -> handle `exit` and
  `env` builtins -> resolve path -> execute.
- `exe.c` — `exe_cmd()`: `fork()` + `execve()` + `wait()` with status
  extraction (`WIFEXITED`/`WIFSIGNALED`/`WIFSTOPPED`).
- `getpath.c`, `getline.c`, `ourstrtok.c`, `strtok.c`, `strdup.c`,
  `free_token.c`, `free_up.c`, `exe_env.c`, `prompt_len.c` — supporting units.
- `mem_leak` — a memory/leak helper artifact; compiled binary `hsh`.

## Technologies
C, POSIX system calls, process management, memory management, manual input/
token parsing (no reliance on libc `getline`/`strtok` in the custom path), shell.

## Backend / low-level concepts practiced
- Process creation and execution (fork/exec/wait).
- PATH resolution and command lookup.
- System-level memory allocation/free discipline.
- Signal/exit status handling.
- Building core infrastructure by hand rather than using libraries.

## Software engineering concepts practiced
Manual string/buffer management (pointer correctness, `free` hygiene),
decomposition into small focused modules with a shared header.

## Lessons supported by work
- Comfort with systems programming and the OS process model.
- Careful memory management is learnable and measurable (a `mem_leak` helper
  was used).

## Reported skill level (accurate, not inflated)
Working-level C systems code on a course project; not claimed as expert/embedded.

## Evidence / key files
`/home/alaabadawii/ALX/simple_shell/shell.h`
`/home/alaabadawii/ALX/simple_shell/mymain.c`
`/home/alaabadawii/ALX/simple_shell/exe.c`
`/home/alaabadawii/ALX/simple_shell/getpath.c`
`/home/alaabadawii/ALX/simple_shell/AUTHORS`