#include <string>
#include <map>
#include <vector>

#include "llvm/IR/DebugInfoMetadata.h"

/****************************** Util for Struct ******************************/
class StructMemberInfo {
private:
  std::string name_;
  std::string ty_name_;
  uint64_t size_;
  uint64_t offset_;
  bool is_ptr_;
  bool is_ary_;

  friend class StructLayout;
  friend class StructLayoutPass;

public:
  StructMemberInfo(llvm::DIDerivedType *node);
  ~StructMemberInfo() {};

  std::string dump(bool with_new_line = false);
};

class StructLayout {
private:
  std::string name_;
  uint64_t size_;
  std::map<uint64_t, StructMemberInfo*> members_;

  friend class StructLayoutPass;

public:
  StructLayout(llvm::DICompositeType *node);
  ~StructLayout();

  std::string dump(bool with_new_line = false);

  inline uint64_t getSize() { return size_; }
  inline std::string getName() { return name_; }
  inline uint64_t getMembSize() { return members_.size(); }
};