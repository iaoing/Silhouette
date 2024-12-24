/**
 * @file DiskContents.h
 * @https://github.com/utsaslab/crashmonkey
 */

#include "DiskContent.h"
#include "../md5/src/md5.h"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <sys/mman.h>

#include <fstream>
#include <iomanip>
#include <sstream>

using std::cout;
using std::endl;
using std::ofstream;
using std::string;

#define PRT_ERR(fmt, ...)                                                      \
  do {                                                                         \
    fprintf(stderr, "%s:%d | " fmt "%s", __FILE__, __LINE__, ##__VA_ARGS__,    \
            strerror(errno));                                                  \
  } while (0);

#define MD5_DIGEST_LENGTH 32

std::string get_md5(std::string fpath) {
  int fd = -1;
  size_t size = 0;
  struct stat statbuf;
  void *file_content = NULL;
  string md5_str;

  // open file.
  fd = open(fpath.c_str(), O_RDONLY);
  if (fd < 0) {
    PRT_ERR("open %s error: ", fpath.c_str());
    goto err_out;
  }

  // get file size.
  if (fstat(fd, &statbuf) < 0) {
    PRT_ERR("fstat %s error: ", fpath.c_str());
    goto err_out;
  }
  size = statbuf.st_size;

  if (size == 0) {
    ;
  } else {
    /* Do not know why mmap file will arise EBUSY error in PMFS */
    // get file content.
    // file_content = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, 0);
    // if (file_content == MAP_FAILED) {
    //     PRT_ERR("mmap %s error: ", fpath.c_str());
    //     close(fd);
    //     goto err_out;
    // }

    file_content = malloc(size);
    if (file_content == NULL) {
      PRT_ERR("malloc %zu error: ", size);
      close(fd);
      goto err_out;
    }
    ssize_t rd_bytes = pread(fd, file_content, size, 0);
    if (rd_bytes != (long int)size) {
      PRT_ERR("pread %zu error: ", size);
      close(fd);
      goto err_out;
    }

    // calculate MD5
    MD5 md5((byte *)file_content, size);
    md5_str = md5.toStr();

    // clear
    // munmap(file_content, size);
    free(file_content);
  }

  close(fd);
  return md5_str;

err_out:
  if (file_content != NULL && file_content != MAP_FAILED) {
    munmap(file_content, size);
  }
  if (fd >= 0) {
    close(fd);
  }
  return "";
}

fileAttributes::fileAttributes() {
  md5sum = "";
  // Initialize dir_attr entries
  memset(&dir_attr, 0, sizeof(dir_attr));
  dir_attr.d_ino = -1;
  dir_attr.d_off = -1;
  dir_attr.d_reclen = -1;
  dir_attr.d_type = -1;
  dir_attr.d_name[0] = '\0';
  // Initialize stat_attr entried
  stat_attr.st_ino = -1;
  stat_attr.st_mode = -1;
  stat_attr.st_nlink = -1;
  stat_attr.st_uid = -1;
  stat_attr.st_gid = -1;
  stat_attr.st_size = -1;
  stat_attr.st_blksize = -1;
  stat_attr.st_blocks = -1;
}

fileAttributes::~fileAttributes() {}

void fileAttributes::set_dir_attr(struct dirent *a) {
  dir_attr.d_ino = a->d_ino;
  dir_attr.d_off = a->d_off;
  dir_attr.d_reclen = a->d_reclen;
  dir_attr.d_type = a->d_type;
  strncpy(dir_attr.d_name, a->d_name, a->d_reclen);
  dir_attr.d_name[a->d_reclen] = '\0';
}

void fileAttributes::set_stat_attr(string path, bool islstat) {
  if (islstat) {
    lstat(path.c_str(), &stat_attr);
  } else {
    stat(path.c_str(), &stat_attr);
  }
  return;
}

void fileAttributes::set_md5sum(string md5) {
  md5sum = md5;
}

bool fileAttributes::compare_dir_attr(struct dirent a) {

  return ((dir_attr.d_ino == a.d_ino) && (dir_attr.d_off == a.d_off) &&
          (dir_attr.d_reclen == a.d_reclen) && (dir_attr.d_type == a.d_type) &&
          (strcmp(dir_attr.d_name, a.d_name) == 0));
}

bool fileAttributes::compare_stat_attr(struct stat a) {

  return ((stat_attr.st_ino == a.st_ino) && (stat_attr.st_mode == a.st_mode) &&
          (stat_attr.st_nlink == a.st_nlink) &&
          (stat_attr.st_uid == a.st_uid) && (stat_attr.st_gid == a.st_gid) &&
          // (stat_attr.st_rdev == a.st_rdev) &&
          // (stat_attr.st_dev == a.st_dev) &&
          (stat_attr.st_size == a.st_size) &&
          (stat_attr.st_blksize == a.st_blksize) &&
          (stat_attr.st_blocks == a.st_blocks));
}

bool fileAttributes::compare_md5sum(string a) { return md5sum.compare(a); }

bool fileAttributes::is_regular_file() { return S_ISREG(stat_attr.st_mode); }

std::string fileAttributes::to_string() {
  // form a stringstream
  std::stringstream os;

  const char HEX_NUMBERS[16] = {
    '0', '1', '2', '3',
    '4', '5', '6', '7',
    '8', '9', 'a', 'b',
    'c', 'd', 'e', 'f'
  };
  char dir_type_hex[3];
  dir_type_hex[0] = HEX_NUMBERS[dir_attr.d_type/16];
  dir_type_hex[1] = HEX_NUMBERS[dir_attr.d_type%16];
  dir_type_hex[2] = '\0';

  // print dir_attr
  // os << "---Directory Atrributes---" << endl;
  os << "Dir_Name   : " << dir_attr.d_name << endl;
  os << "Dir_Inode  : " << dir_attr.d_ino << endl;
  os << "Dir_Offset : " << dir_attr.d_off << endl;
  os << "Dir_Length : " << dir_attr.d_reclen << endl;
  os << "Dir_Type   : 0x" << dir_type_hex << endl;

  // print stat_attr
  // os << "---File Stat Atrributes---" << endl;
  os << "File_Inode     : " << stat_attr.st_ino << endl;
  os << "File_TotalSize : " << stat_attr.st_size << endl;
  os << "File_BlockSize : " << stat_attr.st_blksize << endl;
  os << "File_#Blocks   : " << stat_attr.st_blocks << endl;
  os << "File_#HardLinks: " << stat_attr.st_nlink << endl;
  os << "File_Mode      : " << stat_attr.st_mode << endl;
  os << "File_User ID   : " << stat_attr.st_uid << endl;
  os << "File_Group ID  : " << stat_attr.st_gid << endl;
  os << "File_Device ID : " << stat_attr.st_rdev << endl;
  os << "File_RootDev ID: " << stat_attr.st_dev << endl;

  // print the md5 in hex format.
  // os << "---File MD5---" << endl;
  std::ios init(NULL);
  init.copyfmt(os);
  os << "File_MD5 : 0x";
  if (md5sum.empty()) {
    os << endl;
  } else {
    os << md5sum << endl;
    // for (int i = 0; i < (long)md5sum.size(); ++i) {
    //   if (i == (long)md5sum.size() - 1)
    //     os << std::setfill('0') << std::setw(2) << std::hex
    //        << (unsigned int)(unsigned char)(md5sum[i]) << endl;
    //   else
    //     os << std::setfill('0') << std::setw(2) << std::hex
    //        << (unsigned int)(unsigned char)(md5sum[i]) << " ";
    // }
  }
  os.copyfmt(init);

  if (err_msg.size() > 0) {
    os << err_msg;
  }

  // return
  return os.str();
}

ofstream &operator<<(ofstream &os, fileAttributes &a) {
  os << a.to_string();
  return os;
}

DiskContents::DiskContents() {}

DiskContents::~DiskContents() {}

void DiskContents::reset(string path, std::string desc) {
  max_depth_ = 0;
  mnt_point_ = path;
  desc_ = desc;
  err_msg.empty();
  contents.clear();
}

void DiskContents::get_contents(string path) {
  DIR *directory;
  struct dirent *dir_entry;

  ++max_depth_;
  if (max_depth_ > 100) {
    PRT_ERR("Recursion too depth!")
    err_msg += "error: recursion too depth!\n";
    exit(99);
  }

  // open the directories
  if (!(directory = opendir(path.c_str()))) {
    PRT_ERR("opendir error: ");
    err_msg += "opendir error" + path + " error: " + strerror(errno) + "\n";
    return;
  }

  // get the contents in the directories
  // reset errno as 0 to distinguish error or end of readdir.
  errno = 0;
  if (!(dir_entry = readdir(directory))) {
    if (errno) {
      err_msg += "readdir error" + path + " error: " + strerror(errno) + "\n";
      PRT_ERR("readdir error: ");
    }
    closedir(directory);
    return;
  }

  // traverse the dir.
  do {
    string parent_path(path);
    string filename(dir_entry->d_name);
    string current_path = parent_path + "/" + filename;
    string relative_path = current_path;
    relative_path.erase(0, path.length());
    struct stat statbuf;
    fileAttributes fa;
    // if (stat(current_path.c_str(), &statbuf) == -1) {
    //   PRT_ERR("stat error %s: ", current_path.c_str());
    //   err_msg += "stat error" + current_path + " error: " + strerror(errno) + "\n";
    //   fa.err_msg +=
    //       "stat error" + current_path + " error: " + strerror(errno) + "\n";
    //   contents[current_path] = fa;
    //   continue;
    // }
    if (dir_entry->d_type == DT_DIR) {
      if ((strcmp(dir_entry->d_name, ".") == 0) ||
          (strcmp(dir_entry->d_name, "..") == 0)) {
        // just treat '.' and '..' as a regular file and add it to content map.
        fa.set_dir_attr(dir_entry);
        fa.set_stat_attr(current_path, false);
        contents[current_path] = fa;
        continue;
      }
      fa.set_dir_attr(dir_entry);
      fa.set_stat_attr(current_path, false);
      // contents[relative_path] = fa;
      contents[current_path] = fa;
      // If the entry is a directory and not . or .. make a recursive call
      get_contents(current_path.c_str());
    } else if (dir_entry->d_type == DT_LNK) {
      // compare lstat outputs
      struct stat lstatbuf;
      if (lstat(current_path.c_str(), &lstatbuf) == -1) {
        PRT_ERR("lstat error: ");
        err_msg +=
            "lstat error" + current_path + " error: " + strerror(errno) + "\n";
        fa.err_msg +=
            "lstat error" + current_path + " error: " + strerror(errno) + "\n";
        contents[current_path] = fa;
        continue;
      }
      fa.set_stat_attr(current_path, true);
      // contents[relative_path] = fa;
      contents[current_path] = fa;
    } else if (dir_entry->d_type == DT_REG) {
      fa.set_stat_attr(current_path, false);
      fa.set_md5sum(get_md5(current_path));
      // contents[relative_path] = fa;
      contents[current_path] = fa;
    } else {
      fa.set_stat_attr(current_path, false);
      // contents[relative_path] = fa;
      contents[current_path] = fa;
    }
  } while ((dir_entry = readdir(directory)));
  closedir(directory);
}

std::string DiskContents::toStr() {
  std::ostringstream ostr;

  ostr << "#### " << desc_ << std::endl;

  // output contents.
  int num = 0;
  for (auto &pair : contents) {
    std::ios init(NULL);
    init.copyfmt(ostr);
    ostr << "Content_ID: ";
    ostr << std::setfill('0') << std::setw(5) << ++num << std::endl;
    ostr.copyfmt(init);
    ostr << "Path : " << pair.first << endl;
    ostr << pair.second.to_string() << endl;
  }

  if (err_msg.size() > 0) {
    ostr << err_msg << endl;
  }

  return ostr.str();
}

bool DiskContents::has_err() {
  return this->err_msg.size() > 0;
}

size_t DiskContents::output_contents(std::string ofname) {
  // open output file.
  std::ofstream ofs;
  ofs.open(ofname, std::ofstream::out | std::ofstream::trunc);
  if (!ofs.is_open()) {
    PRT_ERR("ofstream open %s error: ", ofname.c_str());
    return 0;
  }

  ofs << "#### " << desc_ << std::endl;

  // output contents.
  int num = 0;
  for (auto &pair : contents) {
    std::ios init(NULL);
    init.copyfmt(ofs);
    ofs << "Content_ID: ";
    ofs << std::setfill('0') << std::setw(5) << ++num << std::endl;
    ofs.copyfmt(init);
    ofs << "Path : " << pair.first << endl;
    ofs << pair.second.to_string() << endl;
  }

  if (err_msg.size() > 0) {
    ofs << err_msg << endl;
  }

  // how many bytes written.
  size_t wr_bytes = ofs.tellp();

  // close
  ofs.close();

  // return written bytes.
  return wr_bytes;
}

void *get_content(char *path, char *desc) {
  DiskContents ctx;
  ctx.reset(path, desc);
  ctx.get_contents(path);

  std::string ostr = ctx.toStr();
  void *data = malloc(sizeof(char) * ostr.size() + 1);
  memset(data, 0, ostr.size() + 1);
  memcpy(data, ostr.c_str(), ostr.size());

  return data;
}

void free_content_string(void *s) {
  free(s);
}

