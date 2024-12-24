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

# derived variables
LLVM15_LIB_INCLUDE := $(wildcard $(LLVM15_HOME)/lib/clang/15.*/include)
LLVM15_BIN=$(LLVM15_HOME)/bin

CLANG=$(LLVM15_BIN)/clang
CLANGXX=$(LLVM15_BIN)/clang++

CLANG_LINK=$(LLVM15_BIN)/llvm-link
CLANG_OPT=$(LLVM15_BIN)/opt
CLANG_LD=$(LLVM15_BIN)/ld.lld
CLANG_AR=$(LLVM15_BIN)/llvm-ar
CLANG_NM=$(LLVM15_BIN)/llvm-nm
CLANG_STRIP=$(LLVM15_BIN)/llvm-strip
CLANG_OBJCOPY=$(LLVM15_BIN)/llvm-objcopy
CLANG_OBJDUMP=$(LLVM15_BIN)/llvm-objdump
CLANG_READELF=$(LLVM15_BIN)/llvm-readelf
CLANG_HOSTCC=$(LLVM15_BIN)/clang
CLANG_HOSTCXX=$(LLVM15_BIN)/clang++
CLANG_HOSTAR=$(LLVM15_BIN)/llvm-ar
CLANG_HOSTLD=$(LLVM15_BIN)/ld.lld
LLVM_CONFIG=$(LLVM15_BIN)/llvm-config

CC=$(LLVM15_BIN)/clang
CXX=$(LLVM15_BIN)/clang++

# debug flag
DBGFLAGS := -Os -Wall
DBGFLAGS := -O0 -g -ggdb3

# LLVM compiler flags
CXXFLAGS = $(DBGFLAGS) $(shell $(LLVM_CONFIG) --cxxflags)

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

# LLVM linker flags
LDFLAGS = $(CLANG_LIBS) $(shell $(LLVM_CONFIG) --ldflags)

# Name of the Clang tool to build
TOOL_NAME := DumpStructLayout

# Clang tool source files
TOOL_SRC := DumpStructLayout.cpp StructLayout.cpp ../src_info/SrcInfoReader.cpp

# Object files for Clang tool
TOOL_OBJS := $(TOOL_SRC:.cpp=.o)

.PHONY: all clean

# Targets
all: $(TOOL_NAME)

$(TOOL_NAME): $(TOOL_OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $(TOOL_NAME) $(TOOL_OBJS) $(CLANG_LIBS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(TOOL_OBJS) $(TOOL_NAME)