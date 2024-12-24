#include <fstream>
#include <iostream>
#include <string>
#include <unordered_set>

#include "llvm/ADT/Statistic.h"
#include "llvm/Support/CommandLine.h"

#include "DumpStructLayout.h"
#include "StructLayout.h"

using namespace llvm;

/******************************** command line *******************************/
cl::opt<std::string> OutputStLayoutFName_("struct-layout-output-fname",
                                        cl::desc("The output file name to store structure layout information"),
                                        cl::init("-"));

cl::list<std::string>
    StructNameFnameList("struct-info-fname-list",
                         cl::desc("Files that dumpped from source info, which store structure names"),
                         cl::ZeroOrMore);

/********************************* debug type ********************************/
#define DEBUG_TYPE "stlayout"

/********************************** statistic *********************************/
TrackingStatistic statNumDIType_(DEBUG_TYPE, "statNumDIType_",
                                 "Total Number of DIType Instructions");
TrackingStatistic
    statNumDICompType_(DEBUG_TYPE, "statNumDICompType_",
                       "Total Number of statNumDICompType Instructions");

#define ManullyPrintStatMacro(stat)                                            \
  do {                                                                         \
    outs() << format("%10llu", stat.getValue()) << " "                         \
           << format("%25s", stat.getName()) << " - " << stat.getDesc()        \
           << "\n";                                                            \
  } while (0)

static void printAllStatManully() {
  ManullyPrintStatMacro(statNumDIType_);
  ManullyPrintStatMacro(statNumDICompType_);
}

/****************************** register the pass *****************************/
char StructLayoutPass::ID = 0;
static RegisterPass<StructLayoutPass> X("dump-struct-layout", "dump the struct layout");

/******************************* implementation ******************************/
void StructLayoutPass::processStructDI(llvm::DICompositeType *di_node,
                                     std::ofstream &ofile) {
  std::string st_name = di_node->getName().str();

  // analyze the debug info
  if (visited_.count(st_name) == 0 && this->src_info_reader_.inSrcInfoSet(st_name)) {
    StructLayout sti(di_node);
    visited_.insert(st_name);

    // write to file.
    if (ofile.is_open()) {
      ofile << sti.name_ << "," << sti.size_ << "," << sti.members_.size()
            << "\n";
      for (auto pair : sti.members_) {
        auto mem = pair.second;
        ofile << mem->ty_name_ << "," << mem->name_ << "," << mem->offset_
              << "," << mem->size_ << "," << mem->is_ptr_ << "," << mem->is_ary_
              << "\n";
      }
    } else {
      outs() << sti.dump(true);
    }
  }
}

void StructLayoutPass::processDebugInfoMetadata(const Module &M) {
  DebugInfoFinder di_finder;
  di_finder.processModule(M);

  // open file
  std::ofstream ofile;
  if (OutputStLayoutFName_ != "-")
    ofile.open(OutputStLayoutFName_.c_str(), std::ios::out | std::ios::trunc);

  for (auto type : di_finder.types()) {
    ++statNumDIType_;
    if (isa<DICompositeType>(type)) {
      ++statNumDICompType_;
      processStructDI(dyn_cast<DICompositeType>(type), ofile);
    }
  }

  // close file
  if (ofile.is_open()) {
    ofile.close();
  }
}

bool StructLayoutPass::runOnModule(llvm::Module &M) {
  for (auto fname : StructNameFnameList) {
    this->src_info_reader_.addSrcInfoFromFile(fname);
  }

  processDebugInfoMetadata(M);
  printAllStatManully();
  return false;
}