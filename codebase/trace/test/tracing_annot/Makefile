# Compiler options
CXX = g++
CXXFLAGS = -std=c++11 -Wall -Wextra -I../../include

# Files
SRC = test_traceing_annot.cpp ../../src/Si/TracingAnnot.cpp
OBJ = $(SRC:.cpp=.o)
EXE = test_traceing_annot

# Rule to build the executable
$(EXE): $(OBJ)
	$(CXX) $(CXXFLAGS) $^ -o $@

# Rule to build object files
%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Clean rule
clean:
	rm -f $(OBJ) $(EXE)