//===- TracingNoGiri.cpp - Dynamic Slicing Trace Instrumentation Pass -----===//
//
//                          Giri: Dynamic Slicing in LLVM
//
// This file was developed by the LLVM research group and is distributed under
// the University of Illinois Open Source License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//
//
// This files defines passes that are used for dynamic slicing.
//
// TODO:
// Technically, we should support the tracing of signal handlers.  This can
// interrupt the execution of a basic block.
//
//===----------------------------------------------------------------------===//

#include <cxxabi.h>
#include <vector>
#include <string>
#include <iostream>
#include <fstream>

#include "llvm/ADT/Statistic.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Instructions.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Debug.h"
#include "llvm/Transforms/Utils/ModuleUtils.h"
#include "llvm/Demangle/Demangle.h"
#include "llvm/BinaryFormat/Dwarf.h"

#include "Giri/Giri.h"
#include "Utility/Utils.h"
#include "Utility/VectorExtras.h"
#include "Utility/Debug.h"

using namespace giri;
using namespace llvm;

//===----------------------------------------------------------------------===//
//                     Command Line Arguments
//===----------------------------------------------------------------------===//
cl::list<std::string> AnnotRuntimeFuncFnameList("annot-runtime-tracing-fname-list",
                                          cl::desc("Runtime tracing function filename list"),
                                          cl::ZeroOrMore);
cl::list<std::string> AnnotFuncFnameList("annot-func-fname-list",
                                          cl::desc("Function annotation filename list"),
                                          cl::ZeroOrMore);
cl::list<std::string> AnnotStructFnameList("annot-struct-fname-list",
                                          cl::desc("Struct annotation filename list"),
                                          cl::ZeroOrMore);

//===----------------------------------------------------------------------===//
//                        Debug
//===----------------------------------------------------------------------===//
#define DEBUG_TYPE "giri"
#define DEBUG_TYPE_ERR "Debug_ERR"
#define DEBUG_TYPE_WRN "Debug_WRN"
#define DEBUG_TYPE_MSG "Debug_MSG"
#define DEBUG_TYPE_ASM "Debug_ASM"
#define DEBUG_TYPE_CAL "Debug_CAL"
#define DEBUG_TYPE_STA "Instrution_Statistic"

//===----------------------------------------------------------------------===//
//                        Pass Statistics
//===----------------------------------------------------------------------===//

TrackingStatistic statNumBBs_(DEBUG_TYPE_STA, "statNumBBs_", "Number of basic blocks");
TrackingStatistic statNumPHIBBs_(DEBUG_TYPE_STA, "statNumPHIBBs_", "Number of basic blocks with phi nodes");
TrackingStatistic statNumPHINode_(DEBUG_TYPE_STA, "statNumPHINode_", "Number of phi nodes");

TrackingStatistic statNumDBG_(DEBUG_TYPE_STA, "statNumDBG_",
                              "Total Number of DBG Instructions");

TrackingStatistic statNumGEP_(DEBUG_TYPE_STA, "statNumGEP_",
                               "Total Number of GEP Instructions");
TrackingStatistic statNumPMStPtr_(DEBUG_TYPE_STA, "statNumPMStPtr_",
                               "Total Number of PMStPtr Instructions");
TrackingStatistic statNumDRAMStPtr_(DEBUG_TYPE_STA, "statNumDRAMStPtr_",
                               "Total Number of DRAMStPtr Instructions");

TrackingStatistic statNumStartBB_(DEBUG_TYPE_STA, "statNumStartBB_",
                               "Total Number of StartBB Instructions");
TrackingStatistic statNumEndBB_(DEBUG_TYPE_STA, "statNumEndBB_",
                                "Total Number of EndBB Instructions");

TrackingStatistic statNumLoad_(DEBUG_TYPE_STA, "statNumLoad_",
                               "Total Number of Load Instructions");
TrackingStatistic statNumStore_(DEBUG_TYPE_STA, "statNumStore_",
                                "Total Number of Store Instructions");
TrackingStatistic statNumAlloca_(DEBUG_TYPE_STA, "statNumAlloca_",
                                 "Total Number of Alloca Instructions");
TrackingStatistic statNumFence_(DEBUG_TYPE_STA, "statNumFence_",
                                "Total Number of Fence Instructions");
TrackingStatistic statNumCAS_(DEBUG_TYPE_STA, "statNumCAS_",
                              "Total Number of CAS Instructions");
TrackingStatistic statNumRMW_(DEBUG_TYPE_STA, "statNumRMW_",
                              "Total Number of RMW Instructions");

TrackingStatistic statNumMemSet_(DEBUG_TYPE_STA, "statNumMemSet_",
                                 "Total Number of MemSet Instructions");
TrackingStatistic statNumMemMove_(DEBUG_TYPE_STA, "statNumMemMove_",
                                  "Total Number of MemMove Instructions");
TrackingStatistic statNumMemCpy_(DEBUG_TYPE_STA, "statNumMemCpy_",
                                 "Total Number of MemCpy Instructions");
TrackingStatistic
    statNumAtomicMemSet_(DEBUG_TYPE_STA, "statNumMAtomicemSet_",
                         "Total Number of AtomicMemSet Instructions");
TrackingStatistic
    statNumAtomicMemMove_(DEBUG_TYPE_STA, "statNumAtomicMemMove_",
                          "Total Number of AtomicMemMove Instructions");
TrackingStatistic
    statNumAtomicMemCpy_(DEBUG_TYPE_STA, "statNumAtomicMemCpy_",
                         "Total Number of AtomicMemCpy Instructions");
TrackingStatistic statNumAnyMemSet_(DEBUG_TYPE_STA, "statNumMAnyemSet_",
                                    "Total Number of AnyMemSet Instructions");
TrackingStatistic statNumAnyMemMove_(DEBUG_TYPE_STA, "statNumAnyMemMove_",
                                     "Total Number of AnyMemMove Instructions");
TrackingStatistic statNumAnyMemCpy_(DEBUG_TYPE_STA, "statNumAnyMemCpy_",
                                    "Total Number of AnyMemCpy Instructions");

TrackingStatistic statNumInlineAsm_(DEBUG_TYPE_STA, "statNumInlineAsm_",
                                    "Total Number of InlineAsm Instructions");
TrackingStatistic statNumFLUSH_(DEBUG_TYPE_STA, "statNumFLUSH_",
                                "Total Number of FLUSH Instructions");
TrackingStatistic statNumFENCE_(DEBUG_TYPE_STA, "statNumFENCE_",
                                "Total Number of FENCE Instructions");
TrackingStatistic statNumXchgLQ_(DEBUG_TYPE_STA, "statNumXchgLQ_",
                                "Total Number of XCHQG Instructions");
TrackingStatistic statNumMEMSETNT_(DEBUG_TYPE_STA, "statNumMEMSETNT_",
                                   "Total Number of MEMSETNT Instructions");
TrackingStatistic statNumASMCRC32_(DEBUG_TYPE_STA, "statNumASMCRC32_",
                                   "Total Number of CRC32 Instructions");
TrackingStatistic statNumUnknownAsm_(DEBUG_TYPE_STA, "statNumUnknownAsm_",
                                  "Total Number of Unknown Asm Instructions");

TrackingStatistic statNumSelect_(DEBUG_TYPE_STA, "statNumSelect_",
                                  "Total Number of Select Instructions");

TrackingStatistic statNumCall_(DEBUG_TYPE_STA, "statNumCall_",
                               "Total Number of Call Instructions");
TrackingStatistic statNumDaxAccCall_(DEBUG_TYPE_STA, "statNumDaxAccCall_",
                               "Total Number of Call Instructions");
TrackingStatistic statNumRawMemSetCall_(DEBUG_TYPE_STA, "statNumRawMemSetCall_",
                               "Total Number of RawMemSet Call Instructions");
TrackingStatistic statNumRawMemCpyCall_(DEBUG_TYPE_STA, "statNumRawMemCpyCall_",
                               "Total Number of RawMemCpy Call Instructions");
TrackingStatistic statNumRawStrnCmpCall_(DEBUG_TYPE_STA, "statNumRawStrnCmpCall_",
                               "Total Number of RawStrnCmp Call Instructions");
TrackingStatistic statNumUaccessCall_(DEBUG_TYPE_STA, "statNumUaccessCall_",
                               "Total Number of Uaccess Call Instructions");
TrackingStatistic statNumUnknownCall_(DEBUG_TYPE_STA, "statNumUnknownCall_",
                               "Total Number of Call Instructions");

TrackingStatistic statNumDIType_(DEBUG_TYPE_STA, "statNumDIType_",
                               "Total Number of DIType Instructions");
TrackingStatistic statNumDICompType_(DEBUG_TYPE_STA, "statNumDICompType_",
                               "Total Number of statNumDICompType Instructions");

/******************************* Util Functions *******************************/
static bool isUaccessNTCall(const std::string &funcName) {
  if (funcName == "__copy_from_user_inatomic_nocache" ||
             funcName == "__copy_user_nocache") {
  return true;
  } else {
  return false;
  }
}

static bool isUaccessCall(const std::string &funcName) {
  if (funcName == "__copy_from_user_inatomic" ||
             funcName == "__copy_from_user" ||
             funcName == "__copy_to_user_inatomic" ||
             funcName == "__copy_to_user" ||
             funcName == "_copy_from_user" ||
             funcName == "_copy_to_user" ||
             funcName == "copy_from_user" ||
             funcName == "copy_to_user" ||
             funcName == "copy_in_user" ||
             funcName == "strncpy_from_unsafe" ||
             funcName == "__strncpy_from_user" ||
             funcName == "strncpy_from_user" ||
             funcName == "__arch_copy_from_user" ||
             funcName == "__arch_copy_to_user" ||
             funcName == "raw_copy_in_user" ||
             funcName == "copy_user_enhanced_fast_string" ||
             funcName == "copy_user_generic_string" ||
             funcName == "copy_user_generic_unrolled") {
  return true;
  } else {
  return false;
  }
}

static std::string demangleFuncName(const std::string &funcName) {
  return demangle(funcName);
}

static std::string removeCallSuffixNum(const std::string &callName) {
  return callName.substr(0, callName.find('.'));
}

static DILocation *getInstDebugInfoLoc(Instruction *prev) {
  if (prev->getDebugLoc()) {
    return prev->getDebugLoc().get();
  }

  if (prev->getParent()) {
    BasicBlock *BB = prev->getParent();
    for (auto it = BB->begin(); it != BB->end(); ++it) {
      if (it->getDebugLoc()) {
        return it->getDebugLoc().get();
      }
    }
  }

  for (auto &BB : prev->getParent()->getParent()->getBasicBlockList()) {
    for (auto &I : BB.getInstList()) {
      if (I.getDebugLoc()) {
        return I.getDebugLoc().get();
      }
    }
  }

  return nullptr;
}

static void setDebugLocInst(Instruction *call, Instruction *prev) {
  DILocation *DIL = getInstDebugInfoLoc(prev);
  if (DIL) {
    call->setDebugLoc(DebugLoc(DIL));
  } else {
    // outs() << "no debug loc!\n";
    DEBUG_WITH_TYPE(DEBUG_TYPE_WRN, dbgs() << "no debug loc for this instruction\n");
  }
}

#define ManullyPrintStatMacro(stat)                                            \
  do {                                                                         \
    outs() << format("%10llu", stat.getValue()) << " "                         \
           << format("%25s", stat.getName()) << " - " << stat.getDesc()        \
           << "\n";                                                            \
  } while (0)

static void printAllStatManully() {
  ManullyPrintStatMacro(statNumBBs_);
  ManullyPrintStatMacro(statNumPHIBBs_);

  ManullyPrintStatMacro(statNumDBG_);

  ManullyPrintStatMacro(statNumGEP_);
  ManullyPrintStatMacro(statNumPMStPtr_);
  ManullyPrintStatMacro(statNumDRAMStPtr_);

  ManullyPrintStatMacro(statNumStartBB_);
  ManullyPrintStatMacro(statNumEndBB_);

  ManullyPrintStatMacro(statNumLoad_);
  ManullyPrintStatMacro(statNumStore_);
  ManullyPrintStatMacro(statNumAlloca_);
  ManullyPrintStatMacro(statNumFence_);
  ManullyPrintStatMacro(statNumCAS_);
  ManullyPrintStatMacro(statNumRMW_);

  ManullyPrintStatMacro(statNumMemSet_);
  ManullyPrintStatMacro(statNumMemMove_);
  ManullyPrintStatMacro(statNumMemCpy_);
  ManullyPrintStatMacro(statNumAtomicMemSet_);
  ManullyPrintStatMacro(statNumAtomicMemMove_);
  ManullyPrintStatMacro(statNumAtomicMemCpy_);
  ManullyPrintStatMacro(statNumAnyMemSet_);
  ManullyPrintStatMacro(statNumAnyMemMove_);
  ManullyPrintStatMacro(statNumAnyMemCpy_);

  ManullyPrintStatMacro(statNumInlineAsm_);
  ManullyPrintStatMacro(statNumFLUSH_);
  ManullyPrintStatMacro(statNumFENCE_);
  ManullyPrintStatMacro(statNumXchgLQ_);
  ManullyPrintStatMacro(statNumMEMSETNT_);
  ManullyPrintStatMacro(statNumASMCRC32_);
  ManullyPrintStatMacro(statNumUnknownAsm_);

  ManullyPrintStatMacro(statNumCall_);
  ManullyPrintStatMacro(statNumDaxAccCall_);
  ManullyPrintStatMacro(statNumRawMemSetCall_);
  ManullyPrintStatMacro(statNumRawMemCpyCall_);
  ManullyPrintStatMacro(statNumRawStrnCmpCall_);
  ManullyPrintStatMacro(statNumUaccessCall_);
  ManullyPrintStatMacro(statNumUnknownCall_);

  ManullyPrintStatMacro(statNumDIType_);
  ManullyPrintStatMacro(statNumDICompType_);
}

Type *getPointeeTypeByType(Type *t) {
  if (isa<PointerType>(t) && t->getNumContainedTypes() > 0) {
    return t->getContainedType(0);
  }
  if (isa<PointerType>(t) && !t->isOpaquePointerTy()) {
    return t->getNonOpaquePointerElementType();
  }
  return t;
}

/// This method determines whether the given basic block contains any PHI
/// instructions.
///
/// \param  BB - A reference to the Basic Block to analyze.  It is not modified.
/// \return true  if the basic block has one or more PHI instructions,
/// otherwise false.
static bool hasPHI(const BasicBlock & BB) {
  for (BasicBlock::const_iterator I = BB.begin(); I != BB.end(); ++I)
    if (isa<PHINode>(I)) return true;
  return false;
}

//===----------------------------------------------------------------------===//
//                        TracingNoGiri Implementations
//===----------------------------------------------------------------------===//

char TracingNoGiri::ID = 0;

static RegisterPass<TracingNoGiri>
X("trace-no-giri", "Instrument code to trace basic block execution");

/******************************** class utils ********************************/
uint32_t TracingNoGiri::getBBNum(llvm::BasicBlock *BB) {
    return bbNumPass->getID(BB);
}

uint32_t TracingNoGiri::getInstNum(llvm::Instruction *I) {
    if (isa<CallInst>(I)) {
      return lsNumPass->getID(dyn_cast<CallInst>(I));
    } else {
      return lsNumPass->getID(I);
    }
}

void TracingNoGiri::getInstDebugInfoValue(Instruction *I, Value *&line, Value *&col, Value *&fname, Value *&code) {
  DILocation *DIL = nullptr;
  if (I->getDebugLoc()) {
    DIL = I->getDebugLoc().get();
  }
  line = ir_builder_->getInt32(0);
  col = ir_builder_->getInt32(0);
  fname = ConstantPointerNull::get(void_ptr_type_);
  code = ConstantPointerNull::get(void_ptr_type_);
  if (DIL) {
    line = ir_builder_->getInt32(DIL->getLine());
    col = ir_builder_->getInt32(DIL->getColumn());
  }
  if (DIL && DIL->getScope()) {
    fname =  ir_builder_->CreateGlobalStringPtr(DIL->getFilename(), "", 0, I->getParent()->getParent()->getParent());
    if (DIL->getSource().hasValue()) {
      code = ir_builder_->CreateGlobalStringPtr(DIL->getSource().value().take_front(100), "", 0, I->getParent()->getParent()->getParent());
    }
  }
}

/****************************** visit functions ******************************/
/*************************** visit data struct ptr ***************************/
static std::string removeStTpNamePrefix(std::string stname) {
  if (stname.find("struct.") != std::string::npos) {
    return stname.substr(strlen("struct."));
  }
  return stname;
}

static uint64_t getStructSize(llvm::StructType *st, const llvm::DataLayout *layout) {
  const StructLayout *st_lay = layout->getStructLayout(st);
  uint64_t size = st_lay->getSizeInBytes();
  return size;
}

void TracingNoGiri::processStructPtr(GetElementPtrInst &GEP) {
  /**
   * Traditionally, LLVM IR pointer types have contained a pointee type.
   * For example, i32* is a pointer that points to an i32 somewhere in memory.
   * However, due to a lack of pointee type semantics and various issues with
   * having pointee types, there is a desire to remove pointee types from pointers.
   * ref: https://llvm.org/docs/OpaquePointers.html
   */

  /**
   * The Often Misunderstood GEP Instruction
   * ref: https://llvm.org/docs/GetElementPtr.html
   * Example of GEP
   * ref: https://blog.yossarian.net/2020/09/19/LLVMs-getelementptr-by-example
   */

  ++statNumGEP_;
  if (!GEP.getSourceElementType()->isStructTy()) {
    return ;
  }
  uint32_t id = getInstNum(&GEP);

  StructType *st = dyn_cast<StructType>(GEP.getSourceElementType());
  if (!st->hasName()) {
    return ;
  }

  std::string st_name = removeStTpNamePrefix(st->getName().str());
  if (!this->struct_annot_.inAnnotSet(st_name)) {
    return ;
  }
  // outs() << "st: " << st_name << "\n";

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_stptr = GEP.getPointerOperand();
  Value *var_idx;
  uint64_t size = getStructSize(st, data_layout_);
  Value *var_stsize = ir_builder_->getInt64(size);
  Value *var_stname = ir_builder_->CreateGlobalStringPtr(st_name, "", 0, GEP.getParent()->getParent()->getParent());

  if (GEP.getNumOperands() == 3) {
    var_idx = GEP.getOperand(2);
  } else {
    var_idx = ir_builder_->getInt32(9999);
  }

  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&GEP, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  CallInst *call;
  call = CallInst::Create(trace_unknown_struct_ptr_func_, {var_id, var_stptr, var_idx, var_stsize, var_stname, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");

  // if (IsPMStructName(st_name)) {
  //   ++statNumPMStPtr_;
  //   pm_st_map_[st_name] = st;
  //   call = CallInst::Create(trace_pm_struct_ptr_func_, {var_id, var_stptr, var_idx, var_stsize, var_stname, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");
  // } else if (IsDRAMStructName(st_name)) {
  //   ++statNumDRAMStPtr_;
  //   dram_st_map_[st_name] = st;
  //   call = CallInst::Create(trace_dram_struct_ptr_func_, {var_id, var_stptr, var_idx, var_stsize, var_stname, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");
  // } else {
  //   // not the interested struct.
  //   return ;
  // }

  call->insertAfter(&GEP);
  setDebugLocInst(call, &GEP);
}

void TracingNoGiri::visitGetElementPtrInst(llvm::GetElementPtrInst &GEP) {
  processStructPtr(GEP);
}

/****************************** visit dbg calls ******************************/
void TracingNoGiri::resetDeclMap() {
  func_dbg_decl_map_.clear();
}

void TracingNoGiri::processDbgVarStore(llvm::StoreInst *si, llvm::DICompositeType *di_node) {
  std::string st_name = di_node->getName().str();
  if (!this->struct_annot_.inAnnotSet(st_name)) {
    // outs() << __LINE__ << ": " << st_name << ", " << *si << "\n";
    return ;
  }

  uint32_t id = getInstNum(si);
  Value *opv = si->getValueOperand();
  Instruction *itop_inst = NULL;

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_stv = NULL;
  Value *var_stname = ir_builder_->CreateGlobalStringPtr(st_name, "", 0, si->getParent()->getParent()->getParent());
  Value *var_stsize =  ir_builder_->getInt64(di_node->getSizeInBits()/8);

  if (isa<PointerType>(opv->getType())) {
    // use the value if it is pointer type.
    var_stv = opv;
  } else if (ConstantInt *ci = dyn_cast<ConstantInt>(opv)) {
    // we treat ConstantInt as pointer.
    var_stv = ir_builder_->CreateIntToPtr(ci, void_ptr_type_);
    itop_inst = dyn_cast<Instruction>(var_stv);
    assert(itop_inst && "convert CreateIntToPtr to instruction failed!");
  } else {
    // outs() << __LINE__ << ": " << opv->getType()->getTypeID() << ", " << *si << "\n";
    return ;
  }

  CallInst *call = CallInst::Create(trace_dbg_var_store_, {var_id, var_stv, var_stname, var_stsize}, "");

  if (itop_inst != NULL) {
    itop_inst->insertAfter(si);
    call->insertAfter(itop_inst);
    setDebugLocInst(itop_inst, si);
    setDebugLocInst(call, si);
  } else {
    call->insertAfter(si);
    setDebugLocInst(call, si);
  }
}

void TracingNoGiri::processDbgVarLoad1(llvm::LoadInst *li, llvm::DICompositeType *di_node) {
  std::string st_name = di_node->getName().str();
  if (!this->struct_annot_.inAnnotSet(st_name)) {
    // outs() << __LINE__ << ": " << st_name << ", " << *li << "\n";
    return ;
  }

  uint32_t id = getInstNum(li);
  Value *opv = li->getPointerOperand();

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_stv = NULL;
  Value *var_stname = ir_builder_->CreateGlobalStringPtr(st_name, "", 0, li->getParent()->getParent()->getParent());
  Value *var_stsize =  ir_builder_->getInt64(di_node->getSizeInBits()/8);

  if (isa<PointerType>(opv->getType())) {
    // use the value if it is pointer type.
    var_stv = opv;
  }  else {
    // outs() << __LINE__ << ": " << opv->getType()->getTypeID() << ", " << *li << "\n";
    return ;
  }

  CallInst *call = CallInst::Create(trace_dbg_var_store_, {var_id, var_stv, var_stname, var_stsize}, "");

  call->insertAfter(li);
  setDebugLocInst(call, li);
}

void TracingNoGiri::processDbgVarLoad2(llvm::LoadInst *li, llvm::DICompositeType *di_node) {
  std::string st_name = di_node->getName().str();
  if (!this->struct_annot_.inAnnotSet(st_name)) {
    // outs() << __LINE__ << ": " << st_name << ", " << *li << "\n";
    return ;
  }

  uint32_t id = getInstNum(li);
  Value *opv = li;
  Instruction *itop_inst = NULL;

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_stv = NULL;
  Value *var_stname = ir_builder_->CreateGlobalStringPtr(st_name, "", 0, li->getParent()->getParent()->getParent());
  Value *var_stsize =  ir_builder_->getInt64(di_node->getSizeInBits()/8);

  if (isa<PointerType>(opv->getType())) {
    // use the value if it is pointer type.
    var_stv = opv;
  } else if (ConstantInt *ci = dyn_cast<ConstantInt>(opv)) {
    // we treat ConstantInt as pointer.
    var_stv = ir_builder_->CreateIntToPtr(ci, void_ptr_type_);
    itop_inst = dyn_cast<Instruction>(var_stv);
    assert(itop_inst && "convert CreateIntToPtr to instruction failed!");
  } else {
    // outs() << __LINE__ << ": " << opv->getType()->getTypeID() << ", " << *si << "\n";
    return ;
  }

  CallInst *call = CallInst::Create(trace_dbg_var_store_, {var_id, var_stv, var_stname, var_stsize}, "");

  if (itop_inst != NULL) {
    itop_inst->insertAfter(li);
    call->insertAfter(itop_inst);
    setDebugLocInst(itop_inst, li);
    setDebugLocInst(call, li);
  } else {
    call->insertAfter(li);
    setDebugLocInst(call, li);
  }
}

void TracingNoGiri::processDbgVarInst(llvm::Instruction *inst, llvm::DICompositeType *di_node) {
  std::string st_name = di_node->getName().str();
  if (!this->struct_annot_.inAnnotSet(st_name)) {
    // outs() << __LINE__ << ": " << st_name << ", " << *inst << "\n";
    return ;
  }

  if (isa<PHINode>(inst)) {
    // TODO: do we need to handle phi node?
    return ;
  }

  uint32_t id = getInstNum(inst);
  Value *opv = inst;
  Instruction *itop_inst = NULL;

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_stv = NULL;
  Value *var_stname = ir_builder_->CreateGlobalStringPtr(st_name, "", 0, inst->getParent()->getParent()->getParent());
  Value *var_stsize =  ir_builder_->getInt64(di_node->getSizeInBits()/8);

  if (isa<PointerType>(opv->getType())) {
    // use the value if it is pointer type.
    var_stv = opv;
  } else if (ConstantInt *ci = dyn_cast<ConstantInt>(opv)) {
    // we treat ConstantInt as pointer.
    var_stv = ir_builder_->CreateIntToPtr(ci, void_ptr_type_);
    itop_inst = dyn_cast<Instruction>(var_stv);
    assert(itop_inst && "convert CreateIntToPtr to instruction failed!");
  } else {
    // outs() << __LINE__ << ": " << opv->getType()->getTypeID() << ", " << *inst << "\n";
    return ;
  }

  CallInst *call = CallInst::Create(trace_dbg_var_store_, {var_id, var_stv, var_stname, var_stsize}, "");

  if (itop_inst != NULL) {
    itop_inst->insertAfter(inst);
    call->insertAfter(itop_inst);
    setDebugLocInst(itop_inst, inst);
    setDebugLocInst(call, inst);
  } else {
    call->insertAfter(inst);
    setDebugLocInst(call, inst);
  }
}

void TracingNoGiri::processDbgVarLoadStore(llvm::Function &F) {
  std::string mangle_func_name = F.getName().str();
  std::string func_name = demangleFuncName(mangle_func_name);

  if (func_dbg_decl_map_.empty()) {
    return ;
  }

  for (auto &BB : F.getBasicBlockList()) {
    for (auto &I : BB.getInstList()) {
      if (StoreInst *si = dyn_cast<StoreInst>(&I)) {
        Value *var_ptr = si->getPointerOperand();
        if (func_dbg_decl_map_.count(var_ptr) == 0) {
          // outs() << __LINE__ << ": " << *si << "\n";
          continue;
        } else {
          // outs() << __LINE__ << ": " << *si << "\n";
          processDbgVarStore(si, func_dbg_decl_map_[var_ptr]);
        }
      } else if (LoadInst *li = dyn_cast<LoadInst>(&I)) {
        // we also need to check load instruction since the struct pointer could
        // be the intermidate value that be converted as u64.
        // if the ptr is the struct pointer
        if (func_dbg_decl_map_.count(li->getPointerOperand()) == 0) {
          // outs() << __LINE__ << ": " << *li << "\n";
          continue;
        } else {
          // outs() << __LINE__ << ": " << *li << "\n";
          processDbgVarLoad1(li, func_dbg_decl_map_[li->getPointerOperand()]);
        }

        // if the load itself is the struct pointer
        if (func_dbg_decl_map_.count(li) == 0) {
          // outs() << __LINE__ << ": " << *li << "\n";
          continue;
        } else {
          // outs() << __LINE__ << ": " << *li << "\n";
          processDbgVarLoad2(li, func_dbg_decl_map_[li]);
        }
      } else if (Value *val = dyn_cast<Value>(&I)) {
        // LLVM will optimize load of structure ptr as the intermidate value,
        // such as getelementptr, call, instruction. Thus, we also check
        // all instructions to make sure if the struct ptr is used
        // by intermidate value instead of load instruction of concerte var.
        if (func_dbg_decl_map_.count(val) == 0) {
          // outs() << __LINE__ << ": " << I << "\n";
          continue;
        } else {
          // outs() << __LINE__ << ": " << I << "\n";
          processDbgVarInst(&I, func_dbg_decl_map_[val]);
        }
      }
    }
  }
}

void TracingNoGiri::visitDbgDeclareInst(llvm::DbgDeclareInst &DDI) {
  Value *var = DDI.getAddress();
  DILocalVariable *di_var = DDI.getVariable();
  DIType *var_ty = di_var->getType();

  if (!var || !isa<PointerType>(var->getType()) || !var_ty) {
    return ;
  }

  DICompositeType *dic_ty = dyn_cast<DICompositeType>(var_ty);
  DIDerivedType *did_ty = dyn_cast<DIDerivedType>(var_ty);

  if (dic_ty && dic_ty->getTag() == dwarf::Tag::DW_TAG_structure_type) {
    func_dbg_decl_map_.insert({var, dic_ty});
    return ;
  }

  if (!did_ty) {
    return ;
  }

  while ((did_ty->getTag() == dwarf::Tag::DW_TAG_pointer_type ||
          did_ty->getTag() == dwarf::Tag::DW_TAG_typedef) &&
         did_ty->getBaseType() &&
         dyn_cast<DIDerivedType>(did_ty->getBaseType())) {
    did_ty = dyn_cast<DIDerivedType>(did_ty->getBaseType());
  }

  if ((did_ty->getTag() == dwarf::Tag::DW_TAG_pointer_type ||
       did_ty->getTag() == dwarf::Tag::DW_TAG_typedef) &&
      did_ty->getBaseType()) {
    // if this is a pointer to a struct.
    dic_ty = dyn_cast<DICompositeType>(did_ty->getBaseType());
  } else if (did_ty->getTag() == dwarf::Tag::DW_TAG_member && did_ty->getScope()) {
    // if this is a member variable of struct.
    // dic_ty = dyn_cast<DICompositeType>(did_ty->getScope());
  }

  if (dic_ty && dic_ty->getTag() == dwarf::Tag::DW_TAG_structure_type) {
    func_dbg_decl_map_.insert({var, dic_ty});
    return ;
  }
}

void TracingNoGiri::visitDbgValueInst(llvm::DbgValueInst &DVI) {
  std::string mangle_func_name = DVI.getParent()->getParent()->getName().str();
  std::string func_name = demangleFuncName(mangle_func_name);

  Value *var = DVI.getValue();
  DILocalVariable *di_var = DVI.getVariable();
  DIType *var_ty = di_var->getType();

  if (!var || !isa<PointerType>(var->getType()) || !var_ty) {
    return ;
  }

  DICompositeType *dic_ty = dyn_cast<DICompositeType>(var_ty);
  DIDerivedType *did_ty = dyn_cast<DIDerivedType>(var_ty);

  if (dic_ty && dic_ty->getTag() == dwarf::Tag::DW_TAG_structure_type) {
    func_dbg_decl_map_.insert({var, dic_ty});
    return ;
  }

  if (!did_ty) {
    return ;
  }

  while ((did_ty->getTag() == dwarf::Tag::DW_TAG_pointer_type ||
          did_ty->getTag() == dwarf::Tag::DW_TAG_typedef) &&
         did_ty->getBaseType() &&
         dyn_cast<DIDerivedType>(did_ty->getBaseType())) {
    did_ty = dyn_cast<DIDerivedType>(did_ty->getBaseType());
  }

  if ((did_ty->getTag() == dwarf::Tag::DW_TAG_pointer_type ||
       did_ty->getTag() == dwarf::Tag::DW_TAG_typedef) &&
       did_ty->getBaseType()) {
    // if this is a pointer to a struct.
    dic_ty = dyn_cast<DICompositeType>(did_ty->getBaseType());
  } else if (did_ty->getTag() == dwarf::Tag::DW_TAG_member && did_ty->getScope()) {
    // if this is a member variable of struct.
    // dic_ty = dyn_cast<DICompositeType>(did_ty->getScope());
  }

  if (dic_ty && dic_ty->getTag() == dwarf::Tag::DW_TAG_structure_type) {
    func_dbg_decl_map_.insert({var, dic_ty});
    return ;
  }
}

/***************************** visit basic block *****************************/
void TracingNoGiri::processBasicBlock(llvm::BasicBlock &BB) {
  // currently, we do not need basic block information.
  return ;

  ++statNumStartBB_;
  uint32_t id = getBBNum(&BB);

  if (hasPHI(BB)) {
    ++statNumPHIBBs_;
  }

  Instruction *first_inst = &*BB.getFirstInsertionPt();
  Instruction *term_inst = BB.getTerminator();
  if (!term_inst) {
    term_inst = &BB.back();
  }

  std::string func_name = removeCallSuffixNum(demangleFuncName(BB.getParent()->getName().str()));

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = BB.getParent();
  Value *var_lastbb;
  Value *var_func_name = ir_builder_->CreateGlobalStringPtr(func_name, "", 0, BB.getParent()->getParent());
  if (isa<ReturnInst>(term_inst))
     var_lastbb = ir_builder_->getInt32(1);
  else
     var_lastbb = ir_builder_->getInt32(0);

  CallInst *call_start = CallInst::Create(trace_start_bb_, {var_id, var_ptr, var_func_name}, "");
  CallInst *call_end = CallInst::Create(trace_end_bb_, {var_id, var_ptr, var_func_name, var_lastbb}, "");

  call_start->insertBefore(first_inst);
  call_end->insertBefore(term_inst);

  setDebugLocInst(call_start, first_inst);
  setDebugLocInst(call_end, term_inst);
}

/******************************* visit PHI node *******************************/
void TracingNoGiri::visitPHINode(llvm::PHINode &BB) {
    ++statNumPHINode_;
}

/*************************** get tracking sequence ***************************/
Value *TracingNoGiri::getTrackSequence(llvm::Instruction *I, uint64_t incby) {
  Value *var_incby = ir_builder_->getInt64(incby);
  CallInst *call = CallInst::Create(trace_acquire_sequence_, {var_incby}, "");
  call->insertBefore(I);
  setDebugLocInst(call, I);
  return call;
}

/************************* tracking old stored value *************************/
void TracingNoGiri::trackOldStoredValue(llvm::Instruction *I, llvm::Value *var_seq,
                         llvm::Value *var_ptr, llvm::Value *var_size,
                         uint64_t shift) {
  Value *var_shift = ir_builder_->getInt64(shift);

  CallInst *call = CallInst::Create(trace_old_store_value_, {var_seq, var_ptr, var_size, var_shift}, "");

  call->insertBefore(I);
  setDebugLocInst(call, I);
}

/*************** visit memory access and addressing operations ***************/
void TracingNoGiri::visitLoadInst(LoadInst &LI) {
  ++statNumLoad_;
  uint32_t id = getInstNum(&LI);

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = LI.getPointerOperand();
  // getPointerOperand then gettype will return the size of the pointer (8 bytes)
  // instead of the size of the pointee.
  // For load inst, getType() != getPointerOperand()->getType()
  // uint64_t size = data_layout_->getTypeStoreSize(LI.getPointerOperand()->getType());
  uint64_t size = data_layout_->getTypeStoreSize(LI.getType());
  Value *var_size = ir_builder_->getInt64(size);
  // outs() << "load inst size: " << size << "\n";

  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&LI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  CallInst *call = CallInst::Create(trace_load_func_, {var_id, var_ptr, var_size, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");

  call->insertBefore(&LI);
  setDebugLocInst(call, &LI);

}

void TracingNoGiri::visitStoreInst(StoreInst &SI) {
  ++statNumStore_;
  uint32_t id = getInstNum(&SI);

  Value *var_seq = getTrackSequence(&SI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = SI.getPointerOperand();
  uint64_t size = data_layout_->getTypeStoreSize(SI.getValueOperand()->getType());
  Value *var_size = ir_builder_->getInt64(size);

  // trace old stored value
  trackOldStoredValue(&SI, var_seq, var_ptr, var_size, 0);

  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&SI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  CallInst *call = CallInst::Create(trace_store_func_, {var_seq, var_id, var_ptr, var_size, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");

  call->insertAfter(&SI);
  setDebugLocInst(call, &SI);

}

void TracingNoGiri::visitFenceInst(FenceInst &FI) {
  ++statNumFence_;
  uint32_t id = getInstNum(&FI);

  Value *var_id = ir_builder_->getInt32(id);
  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&FI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  CallInst *call = CallInst::Create(trace_fence_func_, {var_id, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");


  call->insertBefore(&FI);
  setDebugLocInst(call, &FI);

}

void TracingNoGiri::visitAtomicCmpXchgInst(llvm::AtomicCmpXchgInst &AI) {
  // This is a read-modify-write instruction.
  // The cmp value and the new value is loaded before xchg instruction,
  // thus, we can omit reads of them here.
  // Since it does not have a side-effect on failure, we just consider it as
  // a store instruction in success.
  // TODO: store only if CAS is success.
  ++statNumCAS_;
  uint32_t id = getInstNum(&AI);

  Value *var_seq = getTrackSequence(&AI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = AI.getPointerOperand();
  uint64_t size = data_layout_->getTypeStoreSize(AI.getPointerOperand()->getType());
  Value *var_size = ir_builder_->getInt64(size);

  // trace old stored value
  trackOldStoredValue(&AI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_xchg_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&AI);
  setDebugLocInst(call, &AI);

  CallInst *fence_call_before = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_before->insertBefore(call);
  setDebugLocInst(fence_call_before, &AI);

  CallInst *fence_call_after = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_after->insertAfter(call);
  setDebugLocInst(fence_call_after, &AI);
}

void TracingNoGiri::visitAtomicRMWInst(llvm::AtomicRMWInst &AI) {
  ++statNumRMW_;
  uint32_t id = getInstNum(&AI);

  Value *var_seq = getTrackSequence(&AI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = AI.getPointerOperand();
  uint64_t size = data_layout_->getTypeStoreSize(AI.getPointerOperand()->getType());
  Value *var_size = ir_builder_->getInt64(size);

  // trace old stored value
  trackOldStoredValue(&AI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_rmw_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&AI);
  setDebugLocInst(call, &AI);

  CallInst *fence_call_before = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_before->insertBefore(call);
  setDebugLocInst(fence_call_before, &AI);

  CallInst *fence_call_after = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_after->insertAfter(call);
  setDebugLocInst(fence_call_after, &AI);
}

/************************ memory intrinsic instructions ***********************/
void TracingNoGiri::visitMemSetInst(llvm::MemSetInst &MSI) {
  ++statNumMemSet_;
  uint32_t id = getInstNum(&MSI);

  Value *var_seq = getTrackSequence(&MSI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = MSI.getDest();
  Value *var_size = MSI.getLength();

  // trace old stored value
  trackOldStoredValue(&MSI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_memset_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&MSI);
  setDebugLocInst(call, &MSI);

}

void TracingNoGiri::visitMemTransferInst(llvm::MemTransferInst &MTI) {
  ++statNumMemMove_;
  uint32_t id = getInstNum(&MTI);

  Value *var_seq = getTrackSequence(&MTI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *dest_ptr = MTI.getDest();
  Value *src_ptr = MTI.getSource();
  Value *var_size = MTI.getLength();

  // trace old stored value
  trackOldStoredValue(&MTI, var_seq, dest_ptr, var_size, 1);

  CallInst *call = CallInst::Create(trace_memtransfer_func_, {var_seq, var_id, dest_ptr, src_ptr, var_size}, "");

  call->insertAfter(&MTI);
  setDebugLocInst(call, &MTI);

}

void TracingNoGiri::visitAtomicMemSetInst(llvm::AtomicMemSetInst &AMSI) {
  ++statNumAtomicMemSet_;
  uint32_t id = getInstNum(&AMSI);

  Value *var_seq = getTrackSequence(&AMSI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = AMSI.getDest();
  Value *var_size = AMSI.getLength();

  // trace old stored value
  trackOldStoredValue(&AMSI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_memset_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&AMSI);
  setDebugLocInst(call, &AMSI);

}

void TracingNoGiri::visitAtomicTransferInst(llvm::AtomicMemTransferInst &AMTI) {
  ++statNumAtomicMemMove_;
  uint32_t id = getInstNum(&AMTI);

  Value *var_seq = getTrackSequence(&AMTI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *dest_ptr = AMTI.getDest();
  Value *src_ptr = AMTI.getSource();
  Value *var_size = AMTI.getLength();

  // trace old stored value
  trackOldStoredValue(&AMTI, var_seq, dest_ptr, var_size, 1);

  CallInst *call = CallInst::Create(trace_memtransfer_func_, {var_seq, var_id, dest_ptr, src_ptr, var_size}, "");

  call->insertAfter(&AMTI);
  setDebugLocInst(call, &AMTI);
}

void TracingNoGiri::visitAnyMemSetInst(llvm::AnyMemSetInst &AMSI) {
  ++statNumAnyMemSet_;
  uint32_t id = getInstNum(&AMSI);

  Value *var_seq = getTrackSequence(&AMSI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = AMSI.getDest();
  Value *var_size = AMSI.getLength();

  // trace old stored value
  trackOldStoredValue(&AMSI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_memset_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&AMSI);
  setDebugLocInst(call, &AMSI);

}

void TracingNoGiri::visitAnyMemTransferInst(llvm::AnyMemTransferInst &AMTI) {
  ++statNumAnyMemMove_;
  uint32_t id = getInstNum(&AMTI);

  Value *var_seq = getTrackSequence(&AMTI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *dest_ptr = AMTI.getDest();
  Value *src_ptr = AMTI.getSource();
  Value *var_size = AMTI.getLength();

  // trace old stored value
  trackOldStoredValue(&AMTI, var_seq, dest_ptr, var_size, 1);

  CallInst *call = CallInst::Create(trace_memtransfer_func_, {var_seq, var_id, dest_ptr, src_ptr, var_size}, "");

  call->insertAfter(&AMTI);
  setDebugLocInst(call, &AMTI);
}

/********************************* inline asm *********************************/
void TracingNoGiri::visitAsmFlush(llvm::CallInst &CI) {
  ++statNumFLUSH_;
  uint32_t id = getInstNum(&CI);

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = CI.getArgOperand(0);
  CallInst *call = CallInst::Create(trace_asm_flush_func_, {var_id, var_ptr}, "");


  call->insertBefore(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::visitAsmFence(llvm::CallInst &CI) {
  ++statNumFENCE_;
  uint32_t id = getInstNum(&CI);

  Value *var_id = ir_builder_->getInt32(id);
  CallInst *call = CallInst::Create(trace_asm_fence_func_, {var_id}, "");

  call->insertBefore(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitAsmXchgLQ(llvm::CallInst &CI) {
  ++statNumXchgLQ_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = CI.getOperand(0);
  uint64_t size = data_layout_->getTypeStoreSize(CI.getOperand(1)->getType());
  Value *var_size = ir_builder_->getInt64(size);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_asm_xchglq_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);

  CallInst *fence_call_before = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_before->insertBefore(call);
  setDebugLocInst(fence_call_before, &CI);

  CallInst *fence_call_after = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
  fence_call_after->insertAfter(call);
  setDebugLocInst(fence_call_after, &CI);
}

void TracingNoGiri::visitAsmCAS(llvm::CallInst &CI) {
  // only works on PMFS and WineFS, other systems may use different cas intrinsic
  if (CI.getNumOperands() == 10) {
    // double compare and swap
    uint32_t id = getInstNum(&CI);

    Value *var_seq = getTrackSequence(&CI, 1);
    Value *var_id = ir_builder_->getInt32(id);
    Value *var_ptr = CI.getOperand(0);
    uint64_t size = 16;
    Value *var_size = ir_builder_->getInt64(size);

    // trace old stored value
    trackOldStoredValue(&CI, var_seq, var_ptr, var_size, 0);

    CallInst *call = CallInst::Create(trace_asm_cas_func_, {var_seq, var_id, var_ptr, var_size}, "");

    call->insertAfter(&CI);
    setDebugLocInst(call, &CI);

    CallInst *fence_call_before = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
    fence_call_before->insertBefore(call);
    setDebugLocInst(fence_call_before, &CI);

    CallInst *fence_call_after = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");
    fence_call_after->insertAfter(call);
    setDebugLocInst(fence_call_after, &CI);
  }
}

void TracingNoGiri::visitAsmMemSetNT(llvm::CallInst &CI) {
  ++statNumMEMSETNT_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = CI.getOperand(0);
  // Value *var_qword = CI.getOperand(1);
  Value *var_size = CI.getOperand(2);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_ptr, var_size, 0);

  CallInst *call = CallInst::Create(trace_asm_memsetnt_func_, {var_seq, var_id, var_ptr, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitAsmCRC32(llvm::CallInst &CI, int length) {
  // the destination of crc32 must be a register, so we do not need to consider
  // the address of it.
  ++statNumASMCRC32_;
  uint32_t id = getInstNum(&CI);

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = CI.getOperand(0);
  Value *var_size = ir_builder_->getInt64(length);

  if (!var_ptr->getType()->isPointerTy()) {
    // the operand of crc32 is not a pointer type, it may be a i64 type
    // and has been load traced in another instruction.
    return ;
  }

  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&CI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  CallInst *call = CallInst::Create(trace_load_func_, {var_id, var_ptr, var_size, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitAsmUnknown(llvm::CallInst &CI, llvm::InlineAsm *IAsm) {
  ++statNumUnknownAsm_;
  uint32_t id = getInstNum(&CI);
  uint32_t num_uaccess_funcs = 0;

  std::string asm_string = IAsm->getAsmString();
  std::replace(asm_string.begin(), asm_string.end(), '\n', ' ');

  asm_string = IAsm->getConstraintString() + " | " + asm_string;
  // errs() << asm_string << "\n";

  // Function *called_func = CI.getCalledFunction();
  // if (!called_func) {
  //   errs() << "No called function\n";
  // } else {
  //   errs() << called_func->getName() << "\n";
  // }

  // for (unsigned i = 0; i < CI.getNumOperands(); ++i) {
  //   errs() << "op #" << i << ": " << *(CI.getOperand(i)) << "\n";
  //   if (llvm::Function *func = dyn_cast<Function>(CI.getOperand(i))) {
  //     errs() << "\t[" << func->getName() << "]\n";
  //   }
  // }

  for (unsigned i = 0; i < CI.getNumOperands(); ++i) {
    if (llvm::Function *func = dyn_cast<Function>(CI.getOperand(i))) {
      if (isUaccessCall(func->getName().str())) {
        num_uaccess_funcs++;
      } else {
        break;
      }
    }
  }

  if (num_uaccess_funcs > 0) {
    // errs() << "This is an uaccess asm call\n\n";
    return visitAsmUaccessCall(CI, IAsm, num_uaccess_funcs);
  }

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_caller_name = ir_builder_->CreateGlobalStringPtr(CI.getCaller()->getName(), "", 0, CI.getParent()->getParent()->getParent());
  Value *var_asm = ir_builder_->CreateGlobalStringPtr(asm_string, "", 0, CI.getParent()->getParent()->getParent());
  Value *line, *col, *fname, *code;
  getInstDebugInfoValue(&CI, line, col, fname, code);
  CallInst *call = CallInst::Create(trace_asm_unknown_func_, {var_id, var_caller_name, fname, line, var_asm}, "");

  call->insertBefore(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitInlineAsm(llvm::CallInst &CI) {
  ++statNumInlineAsm_;
  InlineAsm *IAsm = cast<InlineAsm>(CI.getCalledOperand());
  const std::string &asmStr = IAsm->getAsmString();
  const std::string &asmConstraintStr = IAsm->getConstraintString();

  DEBUG_WITH_TYPE(DEBUG_TYPE_ASM, dbgs() << IAsm << "\n");

  // CLFLUSH and CLFLUSHOPT
  const std::string CLFLUSH("clflush $0");
  // CLWB
  // https://www.intel.com/content/www/us/en/develop/documentation/cpp-compiler-developer-guide-and-reference/top/compiler-reference/intrinsics/intrinsics-for-managing-ext-proc-states-and-regs/intrinsics-to-save-and-restore-ext-proc-states/xsaveopt.html
  // TODO: there are many other `save` instructions.
  // Is it needed?
  const std::string CLWB("xsaveopt $0");
  // MFENCE
  const std::string MFENCE("mfence");
  // SFENCE
  const std::string SFENCE("sfence");
  // Linux compiler barrier
  // https://github.com/torvalds/linux/blob/master/include/linux/compiler.h#L85
  // In our platform, qemu ubuntu kernel 5.1, this compiler barrier will be compiled as
  // call void asm sideeffect "", "~{memory},~{dirflag},~{fpsr},~{flags}"()
  // by clang-, where the asm string is empty and the contraint is above string.
  // Do not if other compilers have different IR result.
  // We did not use memory clobber to check the compiler fence, since some code
  // may also produce the memory clobber.
  const std::string CompilerBarrier("~{memory},~{dirflag},~{fpsr},~{flags}");
  // XCHGQ
  const std::string XCHGQ("xchgq $0,$1");
  const std::string XCHGL("xchgl $0,$1");
  // CAS (compare-and-swap)
  // they may have other kinds of asm keyword, e.g., cmpxchg4, cmpxchgq
  // currently, 'cmpxchg' works on NOVA.
  const std::string CAS("cmpxchg");
  // MEMSETNT
  const std::string MEMSETNT("movnti %rax");
  // crc32 qword, a.k.a., 8 bytes
  const std::string CRC32_QW("crc32q");
  // crc32 byte, a.k.a., 1 byte
  const std::string CRC32_BY("crc32b");

  if (asmStr.find(CLFLUSH) != std::string::npos ||
      asmStr.find(CLWB) != std::string::npos) {
    visitAsmFlush(CI);
  } else if (asmStr.find(MFENCE) != std::string::npos ||
             asmStr.find(SFENCE) != std::string::npos ||
             (asmStr.empty() && asmConstraintStr == CompilerBarrier)) {
    visitAsmFence(CI);
  } else if (asmStr.find(XCHGQ) != std::string::npos ||
             asmStr.find(XCHGL) != std::string::npos) {
    visitAsmXchgLQ(CI);
  } else if (asmStr.find(CAS) != std::string::npos) {
    // outs() << format("CAS number operands: %d", CI.getNumOperands()) << "\n";
    // for (int i = 0; i < CI.getNumOperands(); ++i) {
    //   outs() << *(CI.getOperand(i)) << "\n";
    // }
    if (CI.getNumOperands() == 10) {
      // we only handle the double cas case in PMFS and WineFS
      // since we did not find other CAS cases in NOVA, PMFS, and WineFS.
      visitAsmCAS(CI);
    } else {
      visitAsmUnknown(CI, IAsm);
    }
  } else if (asmStr.find(MEMSETNT) != std::string::npos) {
    visitAsmMemSetNT(CI);
  } else if (asmStr.find(CRC32_QW) != std::string::npos) {
    visitAsmCRC32(CI, 8);
  } else if (asmStr.find(CRC32_BY) != std::string::npos) {
    visitAsmCRC32(CI, 1);
  } else {
    visitAsmUnknown(CI, IAsm);
  }
}

/****************************** branches related ******************************/
void TracingNoGiri::visitSelectInst(llvm::SelectInst &SI) {
  ++statNumSelect_;
  uint32_t id = getInstNum(&SI);

  Value *cond = SI.getCondition();
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_cond;
  if (cond->getType() == int64_type_) {
    var_cond = cond;
  } else if (Constant *C = dyn_cast<Constant>(cond)) {
    var_cond = ConstantExpr::getZExtOrBitCast(C, int64_type_);
  } else {
    var_cond = ir_builder_->CreateZExtOrBitCast(cond, int64_type_, cond->getName());
    ((Instruction *)var_cond)->insertBefore(&SI);
    setDebugLocInst(((Instruction *)var_cond), &SI);
  }

  CallInst *call = CallInst::Create(trace_select_call_, {var_id, var_cond}, "");

  call->insertBefore(&SI);
  setDebugLocInst(call, &SI);
}

/************************ the function call intrinsics ************************/
void TracingNoGiri::visitDaxDirectAccessCall(llvm::CallInst &CI) {
  ++statNumDaxAccCall_;
  uint32_t id = getInstNum(&CI);

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_addr = CI.getArgOperand(3);
  // Value *var_ret = ir_builder_->CreateAdd(&CI, ir_builder_->getInt64(0));
  // var_ret->printAsOperand(outs(), true, CI.getParent()->getParent()->getParent());
  CallInst *call = CallInst::Create(trace_dax_access_func_, {var_id, var_addr, &CI}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::visitRawMemSetCall(llvm::CallInst &CI) {
  ++statNumRawMemSetCall_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_to = CI.getArgOperand(0);
  Value *var_size = CI.getArgOperand(2);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_to, var_size, 0);

  CallInst *call = CallInst::Create(trace_memset_func_, {var_seq, var_id, var_to, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitRawMemCpyCall(llvm::CallInst &CI) {
  ++statNumRawMemCpyCall_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_to = CI.getArgOperand(0);
  Value *var_from = CI.getArgOperand(1);
  Value *var_size = CI.getArgOperand(2);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_to, var_size, 1);

  CallInst *call = CallInst::Create(trace_memtransfer_func_, {var_seq, var_id, var_to, var_from, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);

}

void TracingNoGiri::visitRawStrnCmpCall(llvm::CallInst &CI) {
  ++statNumRawStrnCmpCall_;
  uint32_t id = getInstNum(&CI);

  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(&CI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr1 = CI.getArgOperand(0);
  Value *var_ptr2 = CI.getArgOperand(1);
  Value *var_size = CI.getArgOperand(2);
  CallInst *call1 = CallInst::Create(trace_load_func_, {var_id, var_ptr1, var_size, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");
  CallInst *call2 = CallInst::Create(trace_load_func_, {var_id, var_ptr2, var_size, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");

  call1->insertBefore(&CI);
  call2->insertBefore(&CI);
  setDebugLocInst(call1, &CI);
  setDebugLocInst(call2, &CI);

}

void TracingNoGiri::visitAsmUaccessCall(llvm::CallInst &CI, llvm::InlineAsm *IAsm,
                                        uint32_t num_uaccess_funcs) {
  if (num_uaccess_funcs == 0) {
    return ;
  }

  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_to = CI.getArgOperand(num_uaccess_funcs);
  Value *var_from = CI.getArgOperand(num_uaccess_funcs + 1);
  // Value *var_size = ir_builder_->CreateBitCast(CI.getArgOperand(2), int64_type_);
  CastInst *var_size = CastInst::CreateIntegerCast(CI.getArgOperand(num_uaccess_funcs + 2), int64_type_, false);
  var_size->insertBefore(&CI);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_to, var_size, 1);

  CallInst *call = CallInst::Create(trace_uaccess_call_, {var_seq, var_id, var_to, var_from, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::visitUaccessCall(llvm::CallInst &CI) {
  ++statNumUaccessCall_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_to = CI.getArgOperand(0);
  Value *var_from = CI.getArgOperand(1);
  // Value *var_size = ir_builder_->CreateBitCast(CI.getArgOperand(2), int64_type_);
  CastInst *var_size = CastInst::CreateIntegerCast(CI.getArgOperand(2), int64_type_, false);
  var_size->insertBefore(&CI);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_to, var_size, 1);

  CallInst *call = CallInst::Create(trace_uaccess_call_, {var_seq, var_id, var_to, var_from, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::visitUaccessNTCall(llvm::CallInst &CI) {
  ++statNumUaccessCall_;
  uint32_t id = getInstNum(&CI);

  Value *var_seq = getTrackSequence(&CI, 2);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_to = CI.getArgOperand(0);
  Value *var_from = CI.getArgOperand(1);
  // Value *var_size = ir_builder_->CreateBitCast(CI.getArgOperand(2), int64_type_);
  CastInst *var_size = CastInst::CreateIntegerCast(CI.getArgOperand(2), int64_type_, false);
  var_size->insertBefore(&CI);

  // trace old stored value
  trackOldStoredValue(&CI, var_seq, var_to, var_size, 1);

  CallInst *call = CallInst::Create(trace_uaccess_nt_call_, {var_seq, var_id, var_to, var_from, var_size}, "");

  call->insertAfter(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::visitMutexLockCalls(llvm::CallInst *CI) {
  ++statNumFence_;
  uint32_t id = getInstNum(CI);

  Value *var_id = ir_builder_->getInt32(id);
  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(CI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  // CallInst *call = CallInst::Create(trace_implicit_fence_func_, {var_id, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");
  CallInst *call = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");


  call->insertBefore(CI);
  setDebugLocInst(call, CI);
}

void TracingNoGiri::visitMutexUnlockCalls(llvm::CallInst *CI) {
  ++statNumFence_;
  uint32_t id = getInstNum(CI);

  Value *var_id = ir_builder_->getInt32(id);
  // for debuginfo variable.
  Value *var_dbg_line = ir_builder_->getInt32(0);
  Value *var_dbg_col = ir_builder_->getInt32(0);
  Value *var_dbg_fname = ConstantPointerNull::get(void_ptr_type_);
  Value *var_dbg_code = ConstantPointerNull::get(void_ptr_type_);
  getInstDebugInfoValue(CI, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code);

  // CallInst *call = CallInst::Create(trace_implicit_fence_func_, {var_id, var_dbg_line, var_dbg_col, var_dbg_fname, var_dbg_code}, "");
  CallInst *call = CallInst::Create(trace_implicit_fence_func_, {var_id}, "");


  call->insertAfter(CI);
  setDebugLocInst(call, CI);
}

void TracingNoGiri::visitAllCalls(llvm::CallInst *CI) {
  ++statNumUnknownCall_;

  if (CI->isInlineAsm()) {
    return;
  }

  if (CI->isDebugOrPseudoInst()) {
    // this is dbg function call.
    return;
  }

  // if (CI->isIndirectCall()) {
  //   // the name of indirect call is not matched with the real function name
  //   // it may be called by the function pointer or bind.
  //   return ;
  // }

  // Attempt to get the called function.
  Function *called_func = CI->getCalledFunction();
  if (!called_func) {
    return;
  }

  // if (called_func->isDeclaration() && called_func->isIntrinsic()) {
  //   // dbg or mem related intrinsic.
  //   return;
  // }

  std::string mangle_func_name = called_func->getName().str();
  std::string func_name = demangleFuncName(mangle_func_name);

  if (func_name.find("llvm.lifetime") == 0 ||
      func_name.find("llvm.dbg") == 0 ||
      func_name.find("llvm.objectsize") == 0 ||
      func_name.find("llvm.expect") == 0 ||
      func_name.find("llvm.dbgugtrap") == 0 ||
      func_name.find("llvm.trap") == 0 ||
      func_name.find("llvm.ubsan") == 0 ||
      func_name.find("llvm.assume") == 0 ||
      func_name.find("__asan_load") == 0 ||
      func_name.find("__asan_store") == 0) {
    // llvm intrinsic and other useless function calls
    return ;
  }

  func_name = removeCallSuffixNum(func_name);

  if (this->runtime_tracing_funcs_.inAnnotSet(func_name)) {
    // this call is the instrumented trace function.
    return ;
  }

  if (func_name.find("mutex_lock") == 0 ||
      func_name.find("spin_lock") != std::string::npos) {
    visitMutexLockCalls(CI);
  }
  if (func_name.find("mutex_unlock") == 0 ||
      func_name.find("spin_unlock") != std::string::npos) {
    visitMutexUnlockCalls(CI);
  }

  if (CI->isIndirectCall()) {
    // the name of indirect call is not matched with the real function name
    // it may be called by the function pointer or bind.
    return ;
  }

  uint32_t id = getInstNum(CI);

  std::string caller_name = removeCallSuffixNum(demangleFuncName(CI->getCaller()->getName().str()));
  std::string callee_name = removeCallSuffixNum(demangleFuncName(CI->getCalledFunction()->getName().str()));

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_caller_name = ir_builder_->CreateGlobalStringPtr(caller_name, "", 0, CI->getParent()->getParent()->getParent());
  Value *var_callee_name = ir_builder_->CreateGlobalStringPtr(callee_name, "", 0, CI->getParent()->getParent()->getParent());
  Value *line, *col, *fname, *code;
  getInstDebugInfoValue(CI, line, col, fname, code);
  CallInst *call1 = CallInst::Create(trace_start_call_, {var_id, var_caller_name, var_callee_name, fname, line}, "");
  CallInst *call2 = CallInst::Create(trace_end_call_, {var_id, var_caller_name, var_callee_name, fname, line}, "");

  call1->insertBefore(CI);
  call2->insertAfter(CI);

  setDebugLocInst(call1, CI);
  setDebugLocInst(call2, CI);
}

void TracingNoGiri::visitCallInst(llvm::CallInst &CI) {
  ++statNumCall_;

  if (CI.isInlineAsm()) {
    visitInlineAsm(CI);
    return;
  }

  if (CI.isDebugOrPseudoInst()) {
    // this is dbg function call.
    return;
  }

  // Attempt to get the called function.
  Function *called_func = CI.getCalledFunction();
  if (!called_func) {
    return;
  }

  // if (called_func->isDeclaration() && called_func->isIntrinsic()) {
  //   // dbg or mem related intrinsic.
  //   return;
  // }

  std::string mangle_func_name = called_func->getName().str();
  std::string func_name = demangleFuncName(mangle_func_name);

  if (func_name.find("llvm.lifetime") == 0 ||
      func_name.find("llvm.dbg") == 0 ||
      func_name.find("llvm.objectsize") == 0 ||
      func_name.find("llvm.expect") == 0 ||
      func_name.find("llvm.dbgugtrap") == 0 ||
      func_name.find("llvm.trap") == 0 ||
      func_name.find("llvm.ubsan") == 0 ||
      func_name.find("llvm.assume") == 0 ||
      func_name.find("__asan_load") == 0 ||
      func_name.find("__asan_store") == 0) {
    // llvm intrinsic and other useless function calls
    return ;
  }

  func_name = removeCallSuffixNum(func_name);

  if (this->runtime_tracing_funcs_.inAnnotSet(func_name)) {
    // this call is the instrumented trace function.
    return ;
  }

  if (func_name == "dax_direct_access") {
    return visitDaxDirectAccessCall(CI);
  } else if (isUaccessNTCall(func_name)) {
    // include/linux/uaccess.h functions
    return visitUaccessNTCall(CI);
  } else if (isUaccessCall(func_name)) {
    // include/linux/uaccess.h functions
    return visitUaccessCall(CI);
  } else if (func_name == "__get_user" ||
             func_name == "get_user") {
    // include/linux/uaccess.h functions
    // not needed but we still want to mark it as unknown calls for debugging.
  } else if (func_name == "memcpy" || func_name == "memmove" || \
             func_name == "__memcpy_mcsafe") {
    return visitRawMemCpyCall(CI);
  } else if (func_name == "memset") {
    return visitRawMemSetCall(CI);
  } else if (func_name == "strncpy") {
    return visitRawMemCpyCall(CI);
  } else if (func_name == "strncmp") {
    return visitRawStrnCmpCall(CI);
  } else if (func_name == "nova_flush_buffer" || \
             func_name == "pmfs_flush_buffer") {
    // this is used only for simulating Chipmunk
    return processCentralizedFlushCall(CI);
  }
}

/****************************** special function ******************************/
void TracingNoGiri::processFuncStartEnd(llvm::Function &F, const std::string &func_name) {
  if (F.size() == 0 || F.getEntryBlock().size() == 0) {
    outs() << func_name << ": no place to insert in atomic function\n";
    return ;
  }

  if (visited_func_.count(func_name) > 0) {
    // we have instrumented this function.
    return ;
  }
  visited_func_.insert(func_name);

  // no function numbering pass, so we use the bb id of the entry block.
  uint32_t id = getBBNum(&F.getEntryBlock());

  Instruction *first_inst = &*(F.getEntryBlock().getFirstInsertionPt());
  Instruction *last_inst = &F.back().back();

  if (!isa<ReturnInst>(last_inst)) {
    for (auto &BB : F.getBasicBlockList()) {
      if (isa<ReturnInst>(BB.getTerminator())) {
        last_inst = BB.getTerminator();
        break;
      } else {
        last_inst = &BB.back();
      }
    }
  }

  Value *var_id = ir_builder_->getInt32(id);
  Value *var_ptr = &F;
  Value *var_fnname = ir_builder_->CreateGlobalStringPtr(func_name, "", 0, F.getParent());

  CallInst *call1 = CallInst::Create(trace_start_func_, {var_id, var_ptr, var_fnname}, "");
  call1->insertBefore(first_inst);
  setDebugLocInst(call1, first_inst);

  if (!isa<ReturnInst>(last_inst)) {
    errs() << func_name << ": no return instruction here!\n";
  }

  CallInst *call2 = CallInst::Create(trace_end_func_, {var_id, var_ptr, var_fnname}, "");
  call2->insertBefore(last_inst);
  setDebugLocInst(call2, last_inst);
}

void TracingNoGiri::processCentralizedFlushCall(llvm::CallInst &CI) {
  uint32_t id = getInstNum(&CI);
  std::string caller_name = removeCallSuffixNum(demangleFuncName(CI.getCaller()->getName().str()));

  // errs() << "flush buffer number oprands: " << CI.arg_size() \
  //        << "; called by " << caller_name \
  //        << "\n";
  // for (int i = 0; i < CI.arg_size(); ++i) {
  //   errs() << "----> " << i << ": " << *CI.getArgOperand(i) << "\n";
  // }


  Value *var_seq = getTrackSequence(&CI, 1);
  Value *var_id = ir_builder_->getInt32(id);
  Value *var_addr = CI.getArgOperand(0);
  Value *var_size = NULL;
  // the flush function is optimized even with optnone option.
  // the flushes size is constant 16 + 16 = 32 in pmfs_mkdir
  // when flushing the dentry of '.' and '..' inodes.
  const uint32_t pmfs_mkdir_special_flush_size = 32;
  const uint32_t nova_inode_size = 120;
  const uint32_t winefs_inode_size = 128;

  if (CI.arg_size() >= 2) {
    var_size = CI.getArgOperand(1);
  } else {
    if (caller_name == "pmfs_mkdir") {
      var_size = ir_builder_->getInt32(pmfs_mkdir_special_flush_size);
    } else if (caller_name == "nova_rebuild_inode_finish" || \
               caller_name == "nova_rebuild_file_inode_tree" || \
               caller_name == "memcpy_to_pmem_nocache") {
      var_size = ir_builder_->getInt32(nova_inode_size);
    } else if (caller_name == "pmfs_ioctl") {
      var_size = ir_builder_->getInt32(winefs_inode_size);
    } else {
      errs() << "flush buffer number oprands: " << CI.arg_size() \
             << "; called by " << caller_name \
             << "\n";
      assert(false && "do not have the matched the caller");
    }
  }

  // errs() << *var_seq << "\n";
  // errs() << *var_id << "\n";
  // errs() << *var_addr << "\n";
  // errs() << *var_size << "\n";

  CallInst *call = CallInst::Create(trace_centralized_flush_call_, {var_seq, var_id, var_addr, var_size}, "");

  call->insertBefore(&CI);
  setDebugLocInst(call, &CI);
}

void TracingNoGiri::processInitFSFunc(llvm::Function &F) {
  Instruction *first_inst = &*(F.getEntryBlock().getFirstInsertionPt());
  Instruction *last_inst = &F.back().back();

  if (!isa<ReturnInst>(last_inst)) {
    for (auto &BB : F.getBasicBlockList()) {
      if (isa<ReturnInst>(BB.getTerminator())) {
        last_inst = BB.getTerminator();
        break;
      } else {
        last_inst = &BB.back();
      }
    }
  }
  assert(isa<ReturnInst>(last_inst) && "Cannot find return instruction!");

  CallInst *call1 = CallInst::Create(trace_init_all_, {}, "");

  call1->insertBefore(first_inst);
  setDebugLocInst(call1, first_inst);

  if (!isa<ReturnInst>(last_inst)) {
    errs() << "init module: no return instruction here!\n";
  }

  Value *var_retv = dyn_cast<ReturnInst>(last_inst)->getReturnValue();
  CallInst *call2 = CallInst::Create(trace_destroy_all_, {var_retv}, "");

  call2->insertBefore(last_inst);
  setDebugLocInst(call2, last_inst);
}

void TracingNoGiri::processExitFSFunc(llvm::Function &F) {
  Instruction *first_inst = &*(F.getEntryBlock().getFirstInsertionPt());
  Instruction *last_inst = &F.back().back();

  if (!isa<ReturnInst>(last_inst)) {
    for (auto &BB : F.getBasicBlockList()) {
      if (isa<ReturnInst>(BB.getTerminator())) {
        last_inst = BB.getTerminator();
        break;
      } else {
        last_inst = &BB.back();
      }
    }
  }

  if (!isa<ReturnInst>(last_inst)) {
    errs() << "exit module: no return instruction here!\n";
  }

  Value *var_retv = ir_builder_->getInt32(1);
  CallInst *call1 = CallInst::Create(trace_destroy_all_, {var_retv}, "");

  call1->insertBefore(last_inst);
  setDebugLocInst(call1, last_inst);
}

void TracingNoGiri::visitFunction(llvm::Function &F) {
  if (!func_dbg_decl_map_.empty()) {
    processDbgVarLoadStore(F);
  }

  if (F.isDeclaration() || F.isIntrinsic()) {
    // dbg or mem related intrinsic.
    return;
  }

  std::string mangle_func_name = F.getName().str();
  std::string func_name = demangleFuncName(mangle_func_name);

  if (this->runtime_tracing_funcs_.inAnnotSet(func_name)) {
    return ;
  }

  // no matter if the function is atomic, check it in runtime.
  processFuncStartEnd(F, func_name);

  // capture the loader of the module
  if (func_name == "init_module") {
    processInitFSFunc(F);
  } else if (func_name == "cleanup_module") {
    processExitFSFunc(F);
  }
}

/************************************ init ************************************/
bool TracingNoGiri::doInitialization(Module & M) {
  data_layout_ = new DataLayout(&M);
  ir_builder_ = new llvm::IRBuilder<llvm::NoFolder>(M.getContext(), NoFolder());

  // read runtime tracing functions
  for (auto fname : AnnotRuntimeFuncFnameList) {
    runtime_tracing_funcs_.addAnnotFromFile(fname);
  }
  // read annotations
  for (auto fname : AnnotFuncFnameList) {
    posix_func_annot_.addAnnotFromFile(fname);
  }
  for (auto fname : AnnotStructFnameList) {
    struct_annot_.addAnnotFromFile(fname);
  }


  // some basic types
  int1_type_ = Type::getInt1Ty(M.getContext());
  int8_type_ = Type::getInt8Ty(M.getContext());
  int32_type_ = Type::getInt32Ty(M.getContext());
  int64_type_ = Type::getInt64Ty(M.getContext());
  void_type_ = Type::getVoidTy(M.getContext());
  void_ptr_type_ = Type::getInt8PtrTy(M.getContext());

  // trace acquire sequence function
  trace_acquire_sequence_ =
      M.getOrInsertFunction("trace_acquire_sequence", int64_type_, int64_type_);

  // trace old stored value
  trace_old_store_value_ =
      M.getOrInsertFunction("trace_old_store_value", void_type_, int64_type_, void_ptr_type_, int64_type_, int64_type_);

  // trace init and destroy functions
  trace_init_all_ =
      M.getOrInsertFunction("trace_init_all", void_type_);
  trace_destroy_all_ =
      M.getOrInsertFunction("trace_destroy_all", void_type_, int32_type_);

  // enable mutex or not
  trace_start_func_ =
      M.getOrInsertFunction("trace_start_func", void_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_end_func_ =
      M.getOrInsertFunction("trace_end_func", void_type_, int32_type_, void_ptr_type_, void_ptr_type_);

  // trace BB
  trace_start_bb_ =
      M.getOrInsertFunction("trace_start_bb", void_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_end_bb_ =
      M.getOrInsertFunction("trace_end_bb", void_type_, int32_type_, void_ptr_type_, void_ptr_type_, int32_type_);

  // struct name
  trace_pm_struct_ptr_func_ =
      M.getOrInsertFunction("trace_pm_struct_ptr_inst", void_type_, int32_type_, void_ptr_type_, int32_type_, int64_type_, void_ptr_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_dram_struct_ptr_func_ =
      M.getOrInsertFunction("trace_dram_struct_ptr_inst", void_type_, int32_type_, void_ptr_type_, int32_type_, int64_type_, void_ptr_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_unknown_struct_ptr_func_ =
      M.getOrInsertFunction("trace_unknown_struct_ptr_inst", void_type_, int32_type_, void_ptr_type_, int32_type_, int64_type_, void_ptr_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);

  // dbg
  trace_dbg_var_store_ =
      M.getOrInsertFunction("trace_dbg_var_store", void_type_, int32_type_, void_ptr_type_, void_ptr_type_, int64_type_);

  // load store
  trace_load_func_ =
      M.getOrInsertFunction("trace_load_inst", void_type_, int32_type_, void_ptr_type_, int64_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_store_func_ =
      M.getOrInsertFunction("trace_store_inst", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_fence_func_ =
      M.getOrInsertFunction("trace_fence_inst", void_type_, int32_type_, int32_type_, int32_type_, void_ptr_type_, void_ptr_type_);
  trace_xchg_func_ =
      M.getOrInsertFunction("trace_xchg_inst", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);
  trace_rmw_func_ =
      M.getOrInsertFunction("trace_rmw_inst", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);

  // memory operations
  trace_memset_func_ =
      M.getOrInsertFunction("trace_memset_inst", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);
  trace_memtransfer_func_ =
      M.getOrInsertFunction("trace_memtransfer_inst", void_type_, int64_type_, int32_type_, void_ptr_type_, void_ptr_type_, int64_type_);

  // inline asm trace functions
  trace_asm_flush_func_ =
      M.getOrInsertFunction("trace_inline_asm_flush", void_type_, int32_type_, void_ptr_type_);
  trace_asm_fence_func_ =
      M.getOrInsertFunction("trace_inline_asm_fence", void_type_, int32_type_);
  trace_asm_xchglq_func_ =
      M.getOrInsertFunction("trace_inline_asm_xchglq", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);
  trace_asm_cas_func_ =
      M.getOrInsertFunction("trace_inline_asm_cas", void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);
  trace_asm_memsetnt_func_ = M.getOrInsertFunction("trace_inline_asm_memsetnt",
                                         void_type_, int64_type_, int32_type_, void_ptr_type_, int64_type_);
  trace_asm_unknown_func_ =
      M.getOrInsertFunction("trace_inline_asm_unknown", void_type_, int32_type_, void_ptr_type_, void_ptr_type_, int32_type_, void_ptr_type_);

  trace_implicit_fence_func_ =
      M.getOrInsertFunction("trace_implicit_fence", void_type_, int32_type_);

  // branches related.
  trace_select_call_ =
      M.getOrInsertFunction("trace_select_inst", void_type_, int32_type_, int64_type_);

  // special function calls
  trace_start_call_ =
      M.getOrInsertFunction("trace_start_calls", void_type_, int32_type_, void_ptr_type_, void_ptr_type_, void_ptr_type_, int32_type_);
  trace_end_call_ =
      M.getOrInsertFunction("trace_end_calls", void_type_, int32_type_, void_ptr_type_, void_ptr_type_, void_ptr_type_, int32_type_);
  trace_uaccess_call_ =
      M.getOrInsertFunction("trace_uaccess_calls", void_type_, int64_type_, int32_type_, void_ptr_type_, void_ptr_type_, int64_type_);
  trace_uaccess_nt_call_ =
      M.getOrInsertFunction("trace_uaccess_nt_calls", void_type_, int64_type_, int32_type_, void_ptr_type_, void_ptr_type_, int64_type_);
  trace_dax_access_func_ =
      M.getOrInsertFunction("trace_dax_access", void_type_, int32_type_, void_ptr_type_, int64_type_);

  // centeralized flush function calls
  trace_centralized_flush_call_ =
      M.getOrInsertFunction("trace_centralized_flush", void_type_, int64_type_, int32_type_, void_ptr_type_, int32_type_);

    return true;
}

bool TracingNoGiri::doFinalization(Module & M) {
  if (data_layout_)
    delete data_layout_;
  if (ir_builder_)
    delete ir_builder_;
  return true;
}

bool TracingNoGiri::runOnModule(Module &M) {
  bbNumPass = &getAnalysis<QueryBasicBlockNumbers>();
  lsNumPass = &getAnalysis<QueryLoadStoreNumbers>();

  for (auto &F : M.functions()) {
    // reset the map for this function.
    resetDeclMap();

    if (F.isDeclaration() || F.size() == 0 || F.getEntryBlock().size() == 0) {
      // does not need to visit the function and its children.
      continue;
    }

    for (auto &BB : F.getBasicBlockList()) {
      // visit template will also visit basic block, to distingush instructions
      // and basic blocks, we use another function to visit basic block instead
      // of using the visit template.
      processBasicBlock(BB);
      visit(BB);
    }

    // visit calls here to avoid incorrect instrumentation position.
    for (auto &BB : F.getBasicBlockList()) {
      for (auto &I : BB.getInstList()) {
        if (isa<CallInst>(I)) {
          visitAllCalls(dyn_cast<CallInst>(&I));
        }
      }
    }

    // visit function at last to avoid some tracing happens before the specical
    // function trace handling.
    // outs() << __LINE__ << ": " << F.getName() << ", " << func_dbg_decl_map_.size() << "\n";
    visitFunction(F);
  }

  printAllStatManully();

  return true;
}