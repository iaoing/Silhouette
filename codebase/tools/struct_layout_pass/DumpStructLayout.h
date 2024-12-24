#ifndef __DUMP_STRUCT_INFO_H__
#define __DUMP_STRUCT_INFO_H__

#include <fstream>
#include <iostream>
#include <unordered_set>

#include "llvm/IR/DebugInfo.h"
#include "llvm/Pass.h"

#include "../src_info/SrcInfoReader.h"

class StructLayoutPass : public llvm::ModulePass {
private:
  std::unordered_set<std::string> visited_;
  SrcInfoReader src_info_reader_;

  void processDebugInfoMetadata(const llvm::Module &M);
  void processStructDI(llvm::DICompositeType *di_node, std::ofstream &ofile);

public:
  static char ID;
  StructLayoutPass() : ModulePass(ID){};
  ~StructLayoutPass(){};

  virtual bool runOnModule(llvm::Module &M);

  virtual void getAnalysisUsage(llvm::AnalysisUsage &AU) const {
    AU.setPreservesAll();
  };
};

#endif