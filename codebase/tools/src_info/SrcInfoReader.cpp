#include "SrcInfoReader.h"

#include <iostream>
#include <fstream>
#include <string>
#include <unordered_set>

// Read a unordered_set of strings from a file
static std::unordered_set<std::string> readFromFile(const std::string& filename) {
    std::unordered_set<std::string> rd_set;
    std::ifstream ifs(filename);
    if (ifs.is_open()) {
        std::string str;
        while (std::getline(ifs, str)) {
            rd_set.insert(str);
        }
        ifs.close();
    } else {
        std::cerr << "Error: Unable to open file " << filename << " for reading." << std::endl;
    }
    return rd_set;
}

void SrcInfoReader::addSrcInfoFromFile(std::string fname) {
    auto tmp = readFromFile(fname);
    this->src_info_set_.insert(tmp.begin(), tmp.end());
}

void SrcInfoReader::dbgPrintSrcInfoSet() {
    printf("%s:\n", __FUNCTION__);
    for (auto &str : this->src_info_set_) {
        printf("[%s]; ", str.c_str());
    }
    printf("\n\n");
}

