#include "BaseTestCase.h"

namespace fs_testing {
namespace tests {

using std::string;

using fs_testing::user_tools::api::PassthroughCmFsOps;
using fs_testing::user_tools::api::PosixFsFns;

int BaseTestCase::init_values(string mount_dir, long filesys_size,
                              string ctx_store_dir) {
  this->mnt_dir_ = mount_dir;
  this->filesys_size_ = filesys_size;
  this->ctx_store_dir_ = ctx_store_dir;
  return 0;
}

int BaseTestCase::Run(string dir_name) {
  PosixFsFns posix_fns;
  PassthroughCmFsOps cm(&posix_fns, dir_name);
  this->cm_ = &cm;

  this->setup();

  int ret_val = this->run();
  if (ret_val < 0) {
    return ret_val;
  }

  return 0;
}

int BaseTestCase::get_disk_content(std::string ofname, std::string desc) {
  if (!this->ctx_store_dir_.empty()) {
    this->ctx_.reset(this->mnt_dir_, desc);
    this->ctx_.get_contents(this->mnt_dir_);
    this->ctx_.output_contents(this->ctx_store_dir_ + "/" + ofname);
    if (this->ctx_.has_err()) {
      exit(199);
    }
  }
  return 0;
}

} // namespace tests
} // namespace fs_testing
