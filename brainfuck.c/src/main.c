#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#if defined(_WIN32) || defined(_WIN64)
    #include <conio.h>

    int get_char () {
        /* Windows console getch() reads directly from the console buffer */
        return _getch ();
    }

#else
    #include <termios.h>
    #include <unistd.h>

    int get_char (void) {
        struct termios old_settings, raw_settings;
        int ch;

        /* Save original terminal attributes */
        if (tcgetattr (STDIN_FILENO, &old_settings) == -1) {
            return -1;
        }

        raw_settings = old_settings;

        /* Set raw mode: disable canonical (line-buffered) mode and echo */
        raw_settings.c_lflag &= ~(ICANON | ECHO);
        raw_settings.c_cc[VMIN] = 1;   /* Wait for at least 1 character */
        raw_settings.c_cc[VTIME] = 0;  /* No timeout */

        if (tcsetattr (STDIN_FILENO, TCSADRAIN, &raw_settings) == -1) {
            return -1;
        }

        /* Read 1 character */
        ch = getchar ();

        /* Restore original terminal settings (mirrors Python's `finally`) */
        tcsetattr (STDIN_FILENO, TCSADRAIN, &old_settings);

        return ch;
    }
#endif

#define START_SIZE 128

typedef uint8_t u8;
typedef uint16_t u16;

typedef struct {
    u16* start;
    size_t size;
    size_t capacity;
} Stack;

int Stack_push (Stack* stack, u16 value) {
    if (stack->start == NULL) stack->start = malloc (sizeof (u16));
    if (stack->capacity < stack-> size + 1) {
        stack->start = realloc (stack->start, stack->capacity * 2);
        if (!stack->start) return 1;
        stack->capacity = stack->size * 2;
    }

    stack->start[stack->size] = value;
    stack->size++;

    return 0;
}

u16 Stack_pop (Stack* stack) {
    u16 value = stack->start[stack->size - 1];
    stack->start[stack->size] = 0;
    stack->size--;

    return value;
}

int main (int argc, char** argv) {
    printf ("\n");
    u8 tape[30'000] = {0};
    u16 pos = 0;
    Stack loop_stack = {
		.start = NULL,
		.size = 0,
		.capacity = 0
    };

	char* commands = NULL;
	size_t commands_size = 0;
	ssize_t characters;

    while (1) {
        printf ("\n\033[s:: ");
        characters = getline (&commands, &commands_size, stdin);
        if (characters < 0) {
            free (commands);
            return 1;
        }

        for (size_t i = 0; i < characters; i++) {
			switch (commands[i]) {
		    	case '>':
		    		pos++;
		    		break;
		    	case '<':
		    		pos--;
		    		break;
		    	case '+':
		    		tape[pos]++;
		    		break;
		    	case '-':
		    		tape[pos]--;
		    		break;
		    	case '.':
		    		printf ("%c", tape[pos]);
		    		break;
		    	case ',':
		    		printf ("\033[u\033[K,?");
		    		tape[pos] = (char) getchar ();
		    		printf ("%c", (char) tape[pos]);
		    		break;
		    	case '[':
		    		int push_failed = Stack_push (&loop_stack, pos);
		    		if (push_failed) {
    		    		free (loop_stack.start);
    		    		free (commands);
    		    		return 1;
		    		}
		    		break;
		    	case ']':
		    		pos = Stack_pop (&loop_stack);
		    		break;
		    	default:
		        	break;
			}
        }
    }

    free (loop_stack.start);
    free (commands);

    return 0;
}
