SEQ_DIR := $(SEQ_DIR)
OUT_DIR := $(OUT_DIR)

# function to check all variables are set
check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))

ifneq ($(MAKECMDGOALS),clean)
$(call check_defined, SEQ_DIR)
$(call check_defined, OUT_DIR)
endif

CXX = g++

# DBGFLAGS = -g -O0 -ggdb3
DBGFLAGS = -Os

CXXFLAGS = -std=c++11 -Wall $(DBGFLAGS)
LDFLAGS =

BASE_SRCS = tests/BaseTestCase.cpp user_tools/src/wrapper.cpp ../../tools/disk_content/DiskContent.cpp ../../tools/md5/src/md5.cpp

SEQ_SOURCES = $(wildcard $(SEQ_DIR)/j-lang*.cpp)
SEQ_EXECUTABLES = $(patsubst $(SEQ_DIR)/%.cpp,$(OUT_DIR)/%,$(SEQ_SOURCES))

.PHONY: all clean

all: $(SEQ_EXECUTABLES)

$(OUT_DIR)/%: $(SEQ_DIR)/%.cpp
	$(CXX) $(CXXFLAGS) $< -o $@ $(BASE_SRCS)

seq_exe: \
	$(SEQ_EXECUTABLES)

clean:
	rm -rf $(BINDIR)



