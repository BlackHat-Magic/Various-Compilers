import os
import sys

if os.name == "nt":
	import msvcrt

	def get_char() -> str: # William Gates' special little function
		"""
		Microsoft-flavored get one character
		No, I have not tested it. What do you take me for?
		"""

		return msvcrt.getch().decode("ascii")
else:
	import sys
	import tty
	import termios

	def get_char() -> str: # in fairness Unix doesn't exactly make this easy
		"""
		In a rare twist of fate, the normal-people-flavored way of doing things is *more* annoying than
		the Microsoft-flavored way!
		"""

		fd: int = sys.stdin.fileno()
		old_settings: list = termios.tcgetattr(fd)
		try:
			tty.setraw(sys.stdin.fileno())
			char: str = sys.stdin.read(1)
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
		return char

def main() -> None:
	print()
	tape = bytearray(30_000)
	pos = 0

	while True:
		print()
		commands = input("\033[s:: ")
		loop_stack: list[int] = []

		i = 0
		while True:
			char = commands[i]
			match char:
				case ">":
					pos += 1
				case "<":
					pos -= 1
				case "+":
					if tape[pos] == 255:
						tape[pos] = 0
					else:
						tape[pos] += 1
				case "-":
					if tape[pos] == 0:
						tape[pos] = 255
					else:
						tape[pos] -= 1
				case ".":
					print(chr(tape[pos]), end="")
				case ",":
					sys.stdout.write("\033[u\033[K,?")
					sys.stdout.flush()

					char = get_char()
					print(char)
					tape[pos] = get_char().encode("ascii")[0]
				case "[":
					loop_stack.append(i)
				case "]":
					goto = loop_stack[-1]
					if tape[pos] <= 0:
						loop_stack.pop()
					else:
						i = goto
				case _:
					pass
			i += 1
			if i >= len(commands):
				break

if __name__ == "__main__":
	try:
		main()
	except:
		pass

