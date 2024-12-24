#include <iostream>
#include "Si/TracingAnnot.h"

void test_annot_in(TracingAnnot &annot, std::string key) {
    if (annot.inAnnotSet(key)) {
        std::cout << "[" << key << "] is in the annotation set\n";
    } else {
        std::cout << "[" << key << "] is NOT in the annotation set\n";
    }
}

int main() {
    std::string filename = "sample.annot";
    TracingAnnot annot;

    annot.dbgPrintAnnotSet();
    test_annot_in(annot, "nova_seq_gc");
    test_annot_in(annot, "nova_open");
    test_annot_in(annot, "generic_read_dir");
    test_annot_in(annot, "nova_rmdir");
    test_annot_in(annot, "not_exist_func");
    test_annot_in(annot, "");
    printf("\n\n");

    annot.addAnnotFromFile(filename);
    annot.dbgPrintAnnotSet();

    test_annot_in(annot, "nova_seq_gc");
    test_annot_in(annot, "nova_open");
    test_annot_in(annot, "generic_read_dir");
    test_annot_in(annot, "nova_rmdir");
    test_annot_in(annot, "not_exist_func");
    test_annot_in(annot, "");
    printf("\n\n");

    annot.clear();
    annot.dbgPrintAnnotSet();
    test_annot_in(annot, "nova_seq_gc");
    test_annot_in(annot, "nova_open");
    test_annot_in(annot, "generic_read_dir");
    test_annot_in(annot, "nova_rmdir");
    test_annot_in(annot, "not_exist_func");
    test_annot_in(annot, "");
    printf("\n\n");

    return 0;
}