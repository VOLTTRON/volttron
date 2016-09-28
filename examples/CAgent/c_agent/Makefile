OBJECTS=foo.o
CC=gcc
CFLAGS=-fpic
LDFLAGS=-shared
BINARY=libfoo.so

all: $(BINARY)

$(BINARY): $(OBJECTS)
	$(CC) -o $(BINARY) $(OBJECTS) $(LDFLAGS)

clean:
	$(RM) $(BINARY) $(OBJECTS)

.PHONY: all clean
