#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Frontend/ASTUnit.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/Casting.h"
#include "llvm/Support/CommandLine.h"

#include "llvm/ADT/APInt.h"

#include <dirent.h>

#include <fstream>
#include <iostream>
#include <string>
#include <unordered_set>
#include <vector>

static llvm::cl::OptionCategory DumpSrcInfoCat("Dump Source Code Information");
static llvm::cl::extrahelp
    CommonHelp(clang::tooling::CommonOptionsParser::HelpMessage);
static llvm::cl::opt<std::string> OutputStructName(
    "output_struct_fname",
    llvm::cl::desc("The output file for the struct information (structure names)"),
    llvm::cl::Required, llvm::cl::cat(DumpSrcInfoCat));
static llvm::cl::opt<std::string> OutputVFSFuncName(
    "output_vfs_func_fname",
    llvm::cl::desc("The output file for the VFS function information (function names)"),
    llvm::cl::Required, llvm::cl::cat(DumpSrcInfoCat));
static llvm::cl::opt<std::string> OutputAllFuncName(
    "output_all_func_fname",
    llvm::cl::desc("The output file for all functions information (function names)"),
    llvm::cl::Required, llvm::cl::cat(DumpSrcInfoCat));
static llvm::cl::opt<std::string>
    SrcDir("src_dir", llvm::cl::desc("The directory contains the source files that need to parse"),
           llvm::cl::cat(DumpSrcInfoCat), llvm::cl::init("-"));
static llvm::cl::list<std::string> SrcFiles("src_files",
                                            llvm::cl::desc("Specific source files that need to parse"),
                                            llvm::cl::cat(DumpSrcInfoCat),
                                            llvm::cl::ZeroOrMore);

static std::unordered_set<std::string> VFSOpStructs({
    "inode_operations", "file_operations", "address_space_operations",
    "dentry_operations",
    // "super_operations",

    "struct inode_operations", "struct file_operations",
    "struct address_space_operations", "struct dentry_operations",
    // "struct super_operations",

    "const struct inode_operations", "const struct file_operations",
    "const struct address_space_operations", "const struct dentry_operations",
    // "const struct super_operations",
});

static std::vector<std::string> FillPutSuperFunc({
    "nova_fill_super",
    "nova_put_super",
    "pmfs_fill_super",
    "pmfs_put_super",
});

static std::unordered_set<std::string> StructSet;
static std::unordered_set<std::string> VFSFuncSet;
static std::unordered_set<std::string> AllFuncSet;

bool endsWith(const std::string &str, const std::string &suffix) {
  if (str.length() < suffix.length())
    return false;
  return str.substr(str.length() - suffix.length()) == suffix;
}

std::string getAbsolutePath(const std::string &filename) {
  char resolved_path[PATH_MAX];
  char *ptr = realpath(filename.c_str(), resolved_path);
  if (ptr == nullptr) {
    std::cerr << "Error: Cannot resolve path: " << filename << "\n";
    exit(1);
  }
  return std::string(resolved_path, strlen(resolved_path));
}

std::vector<std::string> getFilesInDir(const std::string &directory) {
  std::vector<std::string> files;

  DIR *dir = opendir(directory.c_str());
  if (dir) {
    dirent *entry;
    while ((entry = readdir(dir)) != nullptr) {
      std::string filename = entry->d_name;
      if (filename != "." && filename != "..") {
        files.push_back(getAbsolutePath(filename));
      }
    }
    closedir(dir);
  } else {
    std::cerr << "Error opening directory " << directory << std::endl;
  }

  return files;
}

void dumpSrcInfoToFile(const std::unordered_set<std::string> &src_info_set,
                     const std::string &fname) {
  std::ofstream outFile(fname, std::ofstream::out | std::ofstream::trunc);
  if (outFile.is_open()) {
    for (const auto &str : src_info_set) {
      outFile << str << '\n';
    }
    outFile.close();
  }
}

class SrcInfo : public clang::RecursiveASTVisitor<SrcInfo> {
private:
  clang::ASTUnit *ast_;
  const std::vector<std::string> src_files_;

public:
  SrcInfo() = delete;

  SrcInfo(clang::ASTUnit *a, const std::vector<std::string> &files)
      : ast_(a), src_files_(files){};

  ~SrcInfo(){};

  clang::ASTContext &getASTContext() { return ast_->getASTContext(); }

  bool inSrcFiles(clang::SourceLocation loc) {
    // avoiding included files.
    std::string fname =
        ast_->getASTContext().getSourceManager().getFilename(loc).str();
    if (fname.size() == 0) {
      return false;
    }

    fname = getAbsolutePath(fname);
    return std::find(src_files_.begin(), src_files_.end(), fname) !=
           src_files_.end();
  }

  bool VisitRecordDecl(clang::RecordDecl *decl) {
    if (!inSrcFiles(decl->getBeginLoc())) {
      return true;
    }

    if (!decl->isThisDeclarationADefinition()) {
      return true;
    }

    // decl->dumpColor();
    std::string decl_name = decl->getDeclName().getAsString();
    if (decl_name.size() == 0) {
      return true;
    }

    // llvm::outs() << "struct [" << decl_name << "]\n";
    // llvm::outs() << "\n";

    StructSet.insert(decl_name);

    return true;
  }

  bool VisitFunctionDecl(clang::FunctionDecl *decl) {
    if (!inSrcFiles(decl->getBeginLoc())) {
      return true;
    }

    if (!decl->isThisDeclarationADefinition()) {
      return true;
    }

    // decl->dumpColor();
    std::string decl_name = decl->getDeclName().getAsString();
    if (decl_name.size() == 0) {
      return true;
    }

    // llvm::outs() << "struct [" << decl_name << "]\n";
    // llvm::outs() << "\n";

    AllFuncSet.insert(decl_name);

    return true;
  }

  bool VisitInitListExpr(clang::InitListExpr *expr) {
    if (!inSrcFiles(expr->getBeginLoc())) {
      return true;
    }

    clang::QualType qty = expr->getType();
    std::string type_name = qty.getAsString();

    // llvm::outs() << "type_name [" << type_name << "]\n";
    // llvm::outs() << "\n";

    if (VFSOpStructs.count(type_name) == 0) {
      // this is not the posix operations
      return true;
    }

    // llvm::outs() << "type_name [" << type_name << "]\n";
    // llvm::outs() << "\n";

    // Iterate through the children of the InitListExpr node
    for (auto it = expr->begin(); it != expr->end(); ++it) {
      if (clang::DesignatedInitExpr *designated_init =
              llvm::dyn_cast<clang::DesignatedInitExpr>(*it)) {

        if (clang::ImplicitCastExpr *cast_expr =
                llvm::dyn_cast<clang::ImplicitCastExpr>(
                    designated_init->getInit())) {

          if (clang::DeclRefExpr *decl_ref =
                  llvm::dyn_cast<clang::DeclRefExpr>(cast_expr->getSubExpr())) {

            if (clang::FunctionDecl *func_decl =
                    llvm::dyn_cast<clang::FunctionDecl>(decl_ref->getDecl())) {
              std::string func_name = func_decl->getNameAsString();

              // llvm::outs() << "func_name [" << func_name << "]\n";
              // llvm::outs() << "\n";

              VFSFuncSet.insert(func_name);
            }
          }
        }
      }
    }

    return true;
  }
};

int main(int argc, const char **argv) {
  int retval = 0;

  auto option =
      clang::tooling::CommonOptionsParser::create(argc, argv, DumpSrcInfoCat);

  auto files = option->getSourcePathList();
  clang::tooling::ClangTool tool(option->getCompilations(), files);

  std::string output_struct_fname = OutputStructName;
  std::string output_vfs_func_fname = OutputVFSFuncName;
  std::string output_all_func_fname = OutputAllFuncName;
  std::string src_dir = SrcDir;
  std::vector<std::string> src_files = SrcFiles;

  if (src_dir != "-") {
    auto tmp = getFilesInDir(src_dir);
    src_files.insert(src_files.end(), tmp.begin(), tmp.end());
  }

  // convert all path to absolute path.
  for (auto &s : src_files) {
    s = getAbsolutePath(s);
  }

  // Build ASTs.
  std::vector<std::unique_ptr<clang::ASTUnit>> asts;
  retval = tool.buildASTs(asts);
  if (retval == 2) {
    llvm::outs() << "error code 2: no error but some files are skipped.\n";
  } else if (retval == 1) {
    llvm::outs() << "error code 1: error occurred.\n";
  }

  // init visitor.
  std::vector<SrcInfo *> src_info;
  for (auto &ast : asts) {
    src_info.push_back(new SrcInfo(ast.get(), src_files));
  }

  // traverse ast.
  for (auto *&visitor : src_info) {
    visitor->TraverseAST(visitor->getASTContext());
  }

  for (auto func_name : FillPutSuperFunc) {
    VFSFuncSet.insert(func_name);
  }

  dumpSrcInfoToFile(StructSet, output_struct_fname);
  dumpSrcInfoToFile(VFSFuncSet, output_vfs_func_fname);
  dumpSrcInfoToFile(AllFuncSet, output_all_func_fname);

  return 0;
}
