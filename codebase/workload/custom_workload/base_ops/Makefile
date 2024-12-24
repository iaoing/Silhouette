CC = gcc
CFLAGS = -g -O0 -Wall -static
all: $(patsubst %.c, %.exe, $(wildcard *.c))

%.exe: %.c
	$(CC) $(CFLAGS) $^ -o $@

clean:
	$(RM) *.o *exe *exe.stackdump