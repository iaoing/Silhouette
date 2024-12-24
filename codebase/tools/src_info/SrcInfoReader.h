/**
 * @file SrcInfoReader.h
 * @brief Used to read annotation filename.
 */

#include <iostream>
#include <fstream>
#include <string>
#include <unordered_set>

class SrcInfoReader {
private:
    std::unordered_set<std::string> src_info_set_;

public:
    SrcInfoReader() {};
    ~SrcInfoReader() {};

    void addSrcInfoFromFile(std::string fname);

    void clear() {
        this->src_info_set_.clear();
    }

    inline bool inSrcInfoSet(std::string &func_name) {
        return (this->src_info_set_.count(func_name) > 0);
    }

    void dbgPrintSrcInfoSet();
};
