/**
 * @file DiskContents.h
 * @https://github.com/utsaslab/crashmonkey
 */

#ifndef DISK_CONTENTS_H
#define DISK_CONTENTS_H

#include <dirent.h> /* Defines DT_* constants */
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#include <fstream>
#include <iostream>
#include <map>
#include <string>
#include <vector>


std::string get_md5(std::string fpath);

class fileAttributes {
public:
  struct dirent dir_attr;
  struct stat stat_attr;
  std::string md5sum;
  std::string err_msg;

  fileAttributes();
  ~fileAttributes();

  void set_dir_attr(struct dirent *a);
  void set_stat_attr(std::string path, bool islstat);
  void set_md5sum(std::string md5);
  bool compare_dir_attr(struct dirent a);
  bool compare_stat_attr(struct stat a);
  bool compare_md5sum(std::string a);
  bool is_regular_file();

  std::string to_string();
};

class DiskContents {
public:
  // Constructor and Destructor
  DiskContents();
  ~DiskContents();

  size_t size() { return contents.size(); };

  void reset(std::string path, std::string desc);
  void get_contents(std::string path);
  std::string toStr();
  size_t output_contents(std::string ofname);
  bool has_err();

private:
  int max_depth_;
  std::string mnt_point_;
  std::string desc_;
  std::string err_msg;
  std::map<std::string, fileAttributes> contents;
};

extern "C" {
  extern void *get_content(char *path, char *desc);
  extern void free_content_string(void *s);
}

#endif // DISK_CONTENTS_H