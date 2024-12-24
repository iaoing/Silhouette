# set from command line
LLVM15_HOME := $(LLVM15_HOME)

# function to check all variables are set
check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))

ifneq ($(MAKECMDGOALS),clean)
$(call check_defined, LLVM15_HOME)
endif

# Clang++ compiler and llvm-config tool
CXX := clang++

# debug flag
DBGFLAGS := -Os -Wall
DBGFLAGS := -O0 -g -ggdb3

LLVM_CONFIG := $(LLVM15_HOME)/bin/llvm-config

LLVM_CXXFLAGS = -Wall -fPIC $(DBGFLAGS) $(shell $(LLVM_CONFIG) --cxxflags)
LLVM_LDFLAGS = -L$(shell $(LLVM_CONFIG) --libdir)
LLVM_LIBS = $(shell $(LLVM_CONFIG) --libs)

# LLVM libraries
CLANG_LIBS = \
	-lclangTooling \
	-lclangFrontend \
	-lclangSerialization \
	-lclangDriver \
	-lclangParse \
	-lclangSema \
	-lclangAnalysis \
	-lclangAST \
	-lclangASTMatchers \
	-lclangEdit \
	-lclangLex \
	-lclangBasic \
	$(shell $(LLVM_CONFIG) --libs) \
	$(shell $(LLVM_CONFIG) --system-libs)

CPP_SRCS := DumpStructLayout.cpp StructLayout.cpp ../src_info/SrcInfoReader.cpp
CPP_OBJS := $(CPP_SRCS:.cpp=.o)

LIB_TARGET := DumpStructLayout.so

.PHONY: all clean

all: $(LIB_TARGET)

%.o: %.cpp %.h
	$(CXX) $(LLVM_CXXFLAGS) -c $< -o $@

%.o: %.cpp
	$(CXX) $(LLVM_CXXFLAGS) -c $< -o $@

$(LIB_TARGET): $(CPP_OBJS)
	$(CXX) $(LLVM_CXXFLAGS) $(LLVM_LDFLAGS) -shared $^ -o $@ $(LLVM_LIBS)

clean:
	rm -rf *.o $(LIB_TARGET)