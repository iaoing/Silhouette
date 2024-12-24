#include <iostream>
#include <sstream>
#include <fstream>
#include <assert.h>

#include "StructLayout.h"

#include "llvm/BinaryFormat/Dwarf.h"
#include "llvm/IR/DebugInfo.h"
#include "llvm/Support/Casting.h"

using namespace llvm;

/***************************** Struct Member Info *****************************/
StructMemberInfo::StructMemberInfo(clang::ASTContext *ctx,
                                   clang::FieldDecl *decl,
                                   uint64_t offset_bits) {
  clang::QualType qt = decl->getType();

  ty_name_ = qt.getAsString();
  name_ = decl->getNameAsString();
  size_bits_ = ctx->getTypeSize(qt);
  size_ = size_bits_ / 8;
  offset_bits_ = offset_bits;
  offset_ = offset_bits_ / 8;
  is_ptr_ = qt.getTypePtr()->isPointerType();
  is_ary_ = qt.getTypePtr()->isArrayType();
}

std::string StructMemberInfo::dump(bool with_new_line) {
  char buf[200];

  std::string tyty;
  if (is_ary_) {
    tyty += "[]";
  }
  if (is_ptr_) {
    tyty += "*";
  }

  snprintf(buf, sizeof(buf), "%-25s %2s %-25s, size: %-5lu, offset: %-5lu",
           ty_name_.c_str(), tyty.c_str(), name_.c_str(), size_, offset_);

  if (with_new_line) {
    return std::string(buf) + "\n";
  }
  return std::string(buf);
}

/******************************** Struct Info ********************************/
StructInfo::StructInfo(clang::ASTContext *ctx, clang::RecordDecl *decl) {
  name_ = decl->getNameAsString();
  size_bits_ = ctx->getTypeSize(decl->getTypeForDecl());
  size_ = size_bits_ / 8;

  uint64_t offset_bits = 0;
  for (clang::FieldDecl *fdecl : decl->fields()) {
    StructMemberInfo *mb = new StructMemberInfo(ctx, fdecl, offset_bits);
    offset_bits += mb->size_bits_;
    members_.insert({mb->offset_bits_, mb});
  }
}

StructInfo::~StructInfo() {
  for (auto pair : members_) {
    delete pair.second;
  }
}

std::string StructInfo::dump(bool with_new_line) {
  std::string str;

  str = name_ + ":\n";

  for (auto it = members_.begin(); it != members_.end(); ++it) {
    str += "\t";
    str += it->second->dump(true);
  }

  if (with_new_line) {
    str += "\n";
  }

  return str;
}


std::string StructInfo::serialize() {
  std::stringstream ss;

  ss << "STRUCT RECORD\n";
  ss << this->name_
     << "," << std::to_string(this->size_bits_)
     << "," << std::to_string(this->size_)
     << "\n";

  for (auto &pair : this->members_) {
    auto *mb = pair.second;
    ss << mb->ty_name_
       << "," << mb->name_
       << "," << std::to_string(mb->size_bits_)
       << "," << std::to_string(mb->size_)
       << "," << std::to_string(mb->offset_bits_)
       << "," << std::to_string(mb->offset_)
       << "," << std::to_string(mb->is_ptr_)
       << "," << std::to_string(mb->is_ary_)
       << "\n";
  }

  return ss.str();
}

void serializeStInfoVec(std::vector<StructInfo *> &vec, const std::string &fname) {
  std::ofstream outFile(fname, std::ofstream::out | std::ofstream::trunc);
  if (outFile.is_open()) {
    for (auto *stinfo : vec) {
      outFile << stinfo->serialize();
    }
    outFile.close();
  } else {
    assert(false && "open file failed!");
  }
}
