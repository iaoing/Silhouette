#include <map>
#include <string>
#include <vector>

#include "clang/AST/ASTContext.h"
#include "clang/AST/Decl.h"

/****************************** Util for Struct ******************************/
class StructMemberInfo {
private:
  std::string ty_name_;
  std::string name_;
  uint64_t size_bits_;   // size in bits
  uint64_t size_;        // in bytes
  uint64_t offset_bits_; // in bites
  uint64_t offset_;      // in bytes
  bool is_ptr_;
  bool is_ary_;

  friend class StructInfo;
  friend class StructInfoPass;

public:
  StructMemberInfo(clang::ASTContext *ctx, clang::FieldDecl *decl,
                   uint64_t offset_bits);
  ~StructMemberInfo(){};

  std::string dump(bool with_new_line = false);
};

class StructInfo {
private:
  std::string name_;
  uint64_t size_bits_;
  uint64_t size_;

  // 
  std::map<uint64_t, StructMemberInfo *> members_;

  friend class StructInfoPass;

public:
  StructInfo(clang::ASTContext *ctx, clang::RecordDecl *decl);
  ~StructInfo();

  std::string dump(bool with_new_line = false);
  std::string serialize();

  inline uint64_t getSize() { return size_; }
  inline std::string getName() { return name_; }
  inline uint64_t getMembSize() { return members_.size(); }
};

void serializeStInfoVec(std::vector<StructInfo *> &vec, const std::string &fname);