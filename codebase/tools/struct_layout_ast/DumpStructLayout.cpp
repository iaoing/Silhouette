#include <dirent.h>

#include <fstream>
#include <iostream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/Frontend/ASTUnit.h"
#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "llvm/Support/Casting.h"
#include "llvm/Support/CommandLine.h"

#include "StructLayout.h"
#include "../src_info/SrcInfoReader.h"

/********************************** Options **********************************/
static llvm::cl::OptionCategory DumpStructInfoCat("Dump Struct Layout Information");

static llvm::cl::extrahelp
    CommonHelp(clang::tooling::CommonOptionsParser::HelpMessage);

static llvm::cl::opt<std::string>
    OutputStLayoutFName("struct-layout-output-fname",
                      llvm::cl::desc("The output file name to store structure layout information"),
                      llvm::cl::cat(DumpStructInfoCat), llvm::cl::init("-"));

static llvm::cl::list<std::string>
    StructNameFnameList("struct-info-fname-list",
                         llvm::cl::desc("Files that dumpped from source info, which store structure names"),
                         llvm::cl::cat(DumpStructInfoCat),
                         llvm::cl::ZeroOrMore);

static llvm::cl::opt<std::string>
    SrcDir("src_dir", llvm::cl::desc("The directory contains all source files"),
           llvm::cl::cat(DumpStructInfoCat), llvm::cl::init("-"));

static llvm::cl::list<std::string> SrcFiles("src_files",
                                            llvm::cl::cat(DumpStructInfoCat),
                                            llvm::cl::desc("Source files"),
                                            llvm::cl::ZeroOrMore);

/****************************** Global variables ******************************/
std::unordered_map<std::string, StructInfo *> glo_stinfo_map;

/******************************* Util functions *******************************/
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

/********************************* stinfo map *********************************/
void dumpStInfoToFile(const std::string &fname) {
  if (fname == "-") {
    return ;
  }

  std::vector<StructInfo *> vec;
  for (auto &pair : glo_stinfo_map) {
    vec.push_back(pair.second);
  }
  serializeStInfoVec(vec, fname);
}

void printStInfo() {
  for (auto &pair : glo_stinfo_map) {
    std::cout << pair.second->dump(true) << std::endl;
  }
}

/***************************** StructInfoVisitor *****************************/
class StructInfoVisitor : public clang::RecursiveASTVisitor<StructInfoVisitor> {
private:
  clang::ASTUnit *ast_;
  const std::vector<std::string> src_files_;
  SrcInfoReader *src_info_;

public:
  StructInfoVisitor() = delete;

  StructInfoVisitor(clang::ASTUnit *a, const std::vector<std::string> &files,
                    SrcInfoReader *src_info)
      : ast_(a), src_files_(files), src_info_(src_info){};

  ~StructInfoVisitor(){};

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
    std::string st_name = decl->getNameAsString();
    if (st_name.size() == 0 || glo_stinfo_map.count(st_name) > 0) {
      return true;
    }

    // llvm::outs() << "struct [" << st_name << "]\n";
    // llvm::outs() << "\n";

    StructInfo *stinfo = new StructInfo(&(ast_->getASTContext()), decl);
    glo_stinfo_map.insert({stinfo->getName(), stinfo});

    return true;
  }
};

int main(int argc, const char **argv) {
  int retval = 0;

  auto option = clang::tooling::CommonOptionsParser::create(argc, argv,
                                                            DumpStructInfoCat);

  auto files = option->getSourcePathList();
  clang::tooling::ClangTool tool(option->getCompilations(), files);

  // options
  std::string output_struct_fname = OutputStLayoutFName;
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

  SrcInfoReader src_info_reader;
  for (auto file : StructNameFnameList) {
    src_info_reader.addSrcInfoFromFile(file);
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
  std::vector<StructInfoVisitor *> st_visitors;
  for (auto &ast : asts) {
    st_visitors.push_back(
        new StructInfoVisitor(ast.get(), src_files, &src_info_reader));
  }

  // traverse ast.
  for (auto *&visitor : st_visitors) {
    visitor->TraverseAST(visitor->getASTContext());
  }

  if (output_struct_fname == "-") {
    printStInfo();
  } else {
    dumpStInfoToFile(output_struct_fname);
  }

  return 0;
}
