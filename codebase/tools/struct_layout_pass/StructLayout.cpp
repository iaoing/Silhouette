#include "StructLayout.h"

#include "llvm/Support/Casting.h"
#include "llvm/IR/DebugInfo.h"
#include "llvm/BinaryFormat/Dwarf.h"

using namespace llvm;

/***************************** Struct Member Info *****************************/
static std::string getTypeName(llvm::DIType *node) {
  if (!node) {
    return "void";
  }

  if (!node->getName().empty()) {
    return node->getName().str();
  }

  if (isa<DIDerivedType>(node)) {
    return getTypeName(dyn_cast<DIDerivedType>(node)->getBaseType());
  } else if (isa<DICompositeType>(node)) {
    return getTypeName(dyn_cast<DICompositeType>(node)->getBaseType());
  } else {
    return "";
  }
}

/***************************** Struct Member Info *****************************/
StructMemberInfo::StructMemberInfo(llvm::DIDerivedType *node) {
  name_ = node->getName().str();
  ty_name_ = getTypeName(node->getBaseType());
  size_ = node->getSizeInBits() / 8;
  offset_ = node->getOffsetInBits() / 8;
  is_ptr_ = (node->getBaseType()->getTag() == dwarf::Tag::DW_TAG_pointer_type);
  is_ary_ = (node->getBaseType()->getTag() == dwarf::Tag::DW_TAG_array_type);
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
StructLayout::StructLayout(llvm::DICompositeType *node) {
  name_ = node->getName().str();
  size_ = node->getSizeInBits() / 8;

  for (auto node : node->getElements()) {
    if (isa<DIDerivedType>(node)) {
      StructMemberInfo *ele = new StructMemberInfo(dyn_cast<DIDerivedType>(node));
      assert(ele && "allocation failed");
      members_.insert({ele->offset_, ele});
    }
  }
}

StructLayout::~StructLayout() {
  for (auto pair : members_) {
    delete pair.second;
  }
}

std::string StructLayout::dump(bool with_new_line) {
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