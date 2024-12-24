#ifndef BASE_TEST_CASE_H
#define BASE_TEST_CASE_H

#include <string>

#include "../../../tools/disk_content/DiskContent.h"
#include "../user_tools/api/wrapper.h"

namespace fs_testing {
namespace tests {

class BaseTestCase {
public:
  int init_values(std::string mount_dir, long filesys_size,
                  std::string ctx_store_dir = "");
  int Run(std::string dir_name);
  int get_disk_content(std::string ofname, std::string desc);

public:
  virtual ~BaseTestCase(){};
  virtual int setup() = 0;
  virtual int run() = 0;

protected:
  std::string mnt_dir_;
  long filesys_size_;
  fs_testing::user_tools::api::CmFsOps *cm_;
  DiskContents ctx_;
  std::string ctx_store_dir_;
};

} // namespace tests
} // namespace fs_testing

#endif