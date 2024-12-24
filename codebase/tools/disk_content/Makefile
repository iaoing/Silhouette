CXX = g++

# DBGFLAGS = -O0 -g -ggdb3
DBGFLAGS = -Os

CXXFLAGS = -std=c++11 -Wall -Wextra $(DBGFLAGS)
LDFLAGS =

.PHONY: all clean

all: DumpDiskContent ctx.so

DumpDiskContent: DumpDiskContent.cpp DiskContent.cpp ../md5/src/md5.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

ctx.so: DiskContent.cpp ../md5/src/md5.cpp
	$(CXX) $(CXXFLAGS) -shared -fPIC -o $@ $^ $(LDFLAGS)

clean:
	rm -f DumpDiskContent *.o *.so