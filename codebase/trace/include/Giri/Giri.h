//===- Giri.h - Dynamic Slicing Pass ----------------------------*- C++ -*-===//
//
//                     Giri: Dynamic Slicing in LLVM
//
// This file was developed by the LLVM research group and is distributed under
// the University of Illinois Open Source License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//
//
// This files defines passes that are used for dynamic slicing.
//
//===----------------------------------------------------------------------===//

#ifndef GIRI_H
#define GIRI_H

#include <deque>
#include <set>
#include <unordered_set>
#include <string>
#include <unordered_map>
#include <vector>

#include "llvm/IR/Dominators.h"
#include "llvm/Analysis/PostDominators.h"
#include "llvm/Pass.h"
#include "llvm/IR/InstVisitor.h"
#include "llvm/IR/DataLayout.h"
#include "llvm/IR/InlineAsm.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/NoFolder.h"
#include "llvm/IR/DebugInfo.h"
#include "llvm/IR/IntrinsicInst.h"

#include "Utility/BasicBlockNumbering.h"
#include "Utility/LoadStoreNumbering.h"

#include "Si/TracingAnnot.h"

using namespace dg;
using namespace llvm;

namespace giri {

/// This class defines an LLVM function pass that instruments a program to
/// generate a trace of its execution usable for dynamic slicing.
class TracingNoGiri : public ModulePass,
                      public InstVisitor<TracingNoGiri> {

private:
  // Pointers to other passes
  const DataLayout *data_layout_;
  llvm::IRBuilder<llvm::NoFolder> *ir_builder_;


  // tracing functions that should not be instrumented.
  TracingAnnot runtime_tracing_funcs_;
  // the posix function that implemented in this file system
  TracingAnnot posix_func_annot_;
  // the struct that implemented in this file syste
  TracingAnnot struct_annot_;  

  std::unordered_map<std::string, llvm::StructType *> pm_st_map_;
  std::unordered_map<std::string, llvm::StructType *> dram_st_map_;

  using dbgDeclMap = std::unordered_map<llvm::Value *, llvm::DICompositeType *>;
  dbgDeclMap func_dbg_decl_map_;

  std::unordered_set<std::string> visited_func_;

  const QueryBasicBlockNumbers *bbNumPass;
  const QueryLoadStoreNumbers  *lsNumPass;

  llvm::Type *int1_type_;
  llvm::Type *int8_type_;
  llvm::Type *int32_type_;
  llvm::Type *int64_type_;
  llvm::Type *void_type_;
  llvm::PointerType *void_ptr_type_;

  llvm::FunctionCallee trace_acquire_sequence_;

  llvm::FunctionCallee trace_old_store_value_;

  llvm::FunctionCallee trace_init_all_;
  llvm::FunctionCallee trace_destroy_all_;

  llvm::FunctionCallee trace_start_func_;
  llvm::FunctionCallee trace_end_func_;

  llvm::FunctionCallee trace_start_bb_;
  llvm::FunctionCallee trace_end_bb_;

  llvm::FunctionCallee trace_pm_struct_ptr_func_;
  llvm::FunctionCallee trace_dram_struct_ptr_func_;
  llvm::FunctionCallee trace_unknown_struct_ptr_func_;

  llvm::FunctionCallee trace_dbg_var_store_;

  llvm::FunctionCallee trace_load_func_;
  llvm::FunctionCallee trace_store_func_;
  llvm::FunctionCallee trace_fence_func_;
  llvm::FunctionCallee trace_xchg_func_;
  llvm::FunctionCallee trace_rmw_func_;
  
  // memory instrinsic have two kinds of args, one is memset which has ptr and 
  // size, another is memtransfer which has fromPtr, toPtr, and size.
  // Thus, we only need two trace function here.
  llvm::FunctionCallee trace_memset_func_;
  llvm::FunctionCallee trace_memtransfer_func_;

  llvm::FunctionCallee trace_asm_flush_func_;
  llvm::FunctionCallee trace_asm_fence_func_;
  llvm::FunctionCallee trace_asm_xchglq_func_;
  llvm::FunctionCallee trace_asm_cas_func_;
  llvm::FunctionCallee trace_asm_memsetnt_func_;
  llvm::FunctionCallee trace_asm_unknown_func_;

  llvm::FunctionCallee trace_implicit_fence_func_;

  // branches related.
  llvm::FunctionCallee trace_select_call_;

  llvm::FunctionCallee trace_start_call_;
  llvm::FunctionCallee trace_end_call_;
  llvm::FunctionCallee trace_uaccess_call_;
  llvm::FunctionCallee trace_uaccess_nt_call_;

  llvm::FunctionCallee trace_dax_access_func_;

  // Centralized Flush Function.
  // They are not used for our design.
  // For testing Chipmunk.
  llvm::FunctionCallee trace_centralized_flush_call_;

public:
  static char ID;
  TracingNoGiri() : data_layout_(nullptr), ir_builder_(nullptr), ModulePass(ID) {}

  /// This method does module level changes needed for adding tracing
  /// instrumentation for dynamic slicing. Specifically, we add the function
  /// prototypes for the dynamic slicing functionality here.
  virtual bool doInitialization(Module &M);
  virtual bool doFinalization(Module &M);

  /// This method starts execution of the dynamic slice tracing instrumentation
  /// pass. It will add code to a function that records the execution of basic
  /// blocks.
  virtual bool runOnModule(Module &M);
  // Since BasciBlockPass has been rmmoved, we run on module and keep the BB
  // function that we can iterater BB from module and pass it to the below 
  // function.
  bool runOnBasicBlock(BasicBlock &BB);

  virtual void getAnalysisUsage(AnalysisUsage &AU) const {
    // AU.addRequired<DataLayout>();
    AU.addRequiredTransitive<QueryBasicBlockNumbers>();
    // AU.addPreserved<QueryBasicBlockNumbers>();

    AU.addRequiredTransitive<QueryLoadStoreNumbers>();
    // AU.addPreserved<QueryLoadStoreNumbers>();
    AU.setPreservesCFG();
  };

public:
  /******************************* data struct *******************************/
  void processStructDI(llvm::DICompositeType *di_node);
  void processDebugInfoMetadata(const llvm::Module &M);

  /******************************** visit GEP ********************************/
  void processStructPtr(llvm::GetElementPtrInst &GEP);
  void visitGetElementPtrInst(llvm::GetElementPtrInst &GEP);

  /***************************** visit dbg calls *****************************/
  void resetDeclMap();
  // used to track declaration of data struct pointer, then tracking
  // the load and store to it.
  void visitDbgDeclareInst(llvm::DbgDeclareInst &DDI);
  void visitDbgValueInst(llvm::DbgValueInst &DVI);
  // iterate all load and store in this function to mark it as a struct access.
  void processDbgVarLoadStore(llvm::Function &F);
  void processDbgVarStore(llvm::StoreInst *si, llvm::DICompositeType *di_node);
  void processDbgVarLoad1(llvm::LoadInst *li, llvm::DICompositeType *di_node);
  void processDbgVarLoad2(llvm::LoadInst *li, llvm::DICompositeType *di_node);
  void processDbgVarInst(llvm::Instruction *inst, llvm::DICompositeType *di_node);

  /**************************** visit basic block ****************************/
  void processBasicBlock(llvm::BasicBlock &BB);

  /****************************** visit PHI node ******************************/
  void visitPHINode(llvm::PHINode &BB);

  /************************** get tracking sequence **************************/
  llvm::Value *getTrackSequence(llvm::Instruction *I, uint64_t incby);

  /************************ tracking old stored value ************************/
  // shift is used to get the correct seq number of store instruction in uaccess, memcpy, etc..
  void trackOldStoredValue(llvm::Instruction *I, llvm::Value *var_seq, llvm::Value *var_ptr, llvm::Value *var_size, uint64_t shift);

  /************** visit memory access and addressing operations **************/
  void visitLoadInst(llvm::LoadInst &LI);
  void visitStoreInst(llvm::StoreInst &SI);
  void visitFenceInst(llvm::FenceInst &AI);
  void visitAtomicCmpXchgInst(llvm::AtomicCmpXchgInst &AI);
  // RMWInst contains xchg, add, sub, and, nand, etc..
  void visitAtomicRMWInst(llvm::AtomicRMWInst &AI);

  /*********************** memory intrinsic instructions **********************/
  // memory instrinsic contains memset, memmove, and memcpy. memset is one kind, 
  // memtransfer is another kind which constains memmove and memcpy.
  // ref: https://llvm.org/doxygen/classllvm_1_1MemIntrinsicBase.html
  void visitMemSetInst(llvm::MemSetInst &MSI);
  void visitMemTransferInst(llvm::MemTransferInst &MTI);
  void visitAtomicMemSetInst(llvm::AtomicMemSetInst &AMSI);
  void visitAtomicTransferInst(llvm::AtomicMemTransferInst &AMTI);
  void visitAnyMemSetInst(llvm::AnyMemSetInst &AMSI);
  void visitAnyMemTransferInst(llvm::AnyMemTransferInst &AMTI);

  /***************************** branches related *****************************/
  void visitSelectInst(llvm::SelectInst &SI);

  /******************************** inline asm ********************************/
  // Inline assembler expressions may only be used as the callee operand of a
  // call or an invoke instruction. Thus, below is a fake visit function.
  void visitInlineAsm(llvm::CallInst &CI);
  void visitAsmFlush(llvm::CallInst &CI);
  void visitAsmFence(llvm::CallInst &CI);
  void visitAsmXchgLQ(llvm::CallInst &CI);
  void visitAsmCAS(llvm::CallInst &CI);
  void visitAsmMemSetNT(llvm::CallInst &CI);
  void visitAsmCRC32(llvm::CallInst &CI, int length);
  void visitAsmUnknown(llvm::CallInst &CI, llvm::InlineAsm *IAsm);  

  /*********************** the function call intrinsics ***********************/
  // Some function calls are extern functions, we need to parse them manully
  // to get useful information.
  void visitDaxDirectAccessCall(llvm::CallInst &CI);
  void visitRawMemSetCall(llvm::CallInst &CI);
  void visitRawMemCpyCall(llvm::CallInst &CI);
  void visitRawStrnCmpCall(llvm::CallInst &CI);
  void visitAsmUaccessCall(llvm::CallInst &CI, llvm::InlineAsm *IAsm, uint32_t num_uaccess_funcs);
  void visitUaccessCall(llvm::CallInst &CI);
  void visitUaccessNTCall(llvm::CallInst &CI);
  // mutex lock and unlock is a kind of fence instruction
  void visitMutexLockCalls(llvm::CallInst *CI);
  void visitMutexUnlockCalls(llvm::CallInst *CI);
  void visitAllCalls(llvm::CallInst *CI);
  void visitCallInst(llvm::CallInst &CI);

  /******************** centralized flushing function call ********************/
  // only used for testing Chipmunk
  // will not be used in our platform
  void processCentralizedFlushCall(llvm::CallInst &CI);

  /***************************** special function *****************************/
  void processInitFSFunc(llvm::Function &F);
  void processExitFSFunc(llvm::Function &F);
  void processFuncStartEnd(llvm::Function &F, const std::string &func_name);
  void visitFunction(llvm::Function &F);

private:
  // utils
  uint32_t getBBNum(llvm::BasicBlock *BB);
  uint32_t getInstNum(llvm::Instruction *I);
  void getInstDebugInfoValue(llvm::Instruction *I, llvm::Value *&line, llvm::Value *&col, llvm::Value *&fname, llvm::Value *&code);
};

} // END namespace giri

#endif
