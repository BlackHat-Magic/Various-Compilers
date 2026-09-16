bf-c action="repl":
	#!/bin/bash
	if [ ! -f ./brainfuck.c/build/bf ]; then
		mkdir -p ./brainfuck.c/build
		gcc ./brainfuck.c/src/main.c -o ./brainfuck.c/build/bf
	fi
	if [ "{{action}}" == "repl" ]; then
		./brainfuck.c/build/bf
	fi

bf-py:
	@uv run --project ./brainfuck.py repl
