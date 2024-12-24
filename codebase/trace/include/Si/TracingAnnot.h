/**
 * @file TracingAnnot.h
 * @brief Used to read annotation filename.
 */

#ifndef SILHOUETTE_TRACING_ANNOT_H
#define SILHOUETTE_TRACING_ANNOT_H

#include <iostream>
#include <fstream>
#include <string>
#include <unordered_set>

class TracingAnnot {
private:
    std::unordered_set<std::string> annot_set_;

public:
    TracingAnnot() {};
    ~TracingAnnot() {};

    void addAnnotFromFile(std::string fname);
    
    void clear() {
        this->annot_set_.clear();
    }

    inline bool inAnnotSet(std::string &func_name) {
        return (this->annot_set_.count(func_name) > 0);
    }

    void dbgPrintAnnotSet();
};

#endif