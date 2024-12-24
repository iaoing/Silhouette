CXX = g++

# DBGFLAGS = -O0 -g -ggdb3
DBGFLAGS = -Os

CXXFLAGS = -std=c++11 -Wall -Wextra $(DBGFLAGS) -shared -fPIC
LDFLAGS =

.PHONY: all clean

all: md5.so

md5.so: src/md5.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f *.o *.so