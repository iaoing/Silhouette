#include "../api/wrapper.h"

#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <utility>
#include <iostream>

namespace fs_testing {
namespace user_tools {
namespace api {

using std::pair;
using std::shared_ptr;
using std::string;
using std::tuple;
using std::unordered_map;
using std::vector;

using std::cout;
using std::endl;

// Super ugly defines to do compile-time string concatonation X times...
#define REP0(x)
#define REP1(x)     x
#define REP2(x)     REP1(x) x
#define REP3(x)     REP2(x) x
#define REP4(x)     REP3(x) x
#define REP5(x)     REP4(x) x
#define REP6(x)     REP5(x) x
#define REP7(x)     REP6(x) x
#define REP8(x)     REP7(x) x
#define REP9(x)     REP8(x) x
#define REP10(x)    REP9(x) x

#define REP(hundreds, tens, ones, x) \
  REP##hundreds(REP10(REP10(x))) \
  REP##tens(REP10(x)) \
  REP##ones(x)

namespace {

// We want exactly 4k of data for this.
static const unsigned int kTestDataSize = 4096;
// 4K of data plus one terminating byte.
static constexpr char kTestDataBlock[kTestDataSize + 1] =
  REP(1, 2, 8, "abcdefghijklmnopqrstuvwxyz123456");

}  // namespace

/******************************************************************************/
/********************************* PosixFsFns *********************************/
/******************************************************************************/

int PosixFsFns::FnMknod(const std::string &pathname, mode_t mode, dev_t dev) {
	return mknod(pathname.c_str(), mode, dev);
}

int PosixFsFns::FnMkdir(const std::string &pathname, mode_t mode) {
	return mkdir(pathname.c_str(), mode);
}

int PosixFsFns::FnOpen(const std::string &pathname, int flags) {
	return open(pathname.c_str(), flags);
}

int PosixFsFns::FnOpen2(const std::string &pathname, int flags, mode_t mode) {
  return open(pathname.c_str(), flags, mode);
}

int PosixFsFns::FnChmod(const std::string &path, mode_t mode) {
  return chmod(path.c_str(), mode);
}

off_t PosixFsFns::FnLseek(int fd, off_t offset, int whence) {
	return lseek(fd, offset, whence);
}

ssize_t PosixFsFns::FnWrite(int fd, const void *buf, size_t count) {
  return write(fd, buf, count);
}

ssize_t PosixFsFns::FnPwrite(int fd, const void *buf, size_t count,
    off_t offset) {
	return pwrite(fd, buf, count, offset);
}

void * PosixFsFns::FnMmap(void *addr, size_t length, int prot, int flags,
    int fd, off_t offset) {
	return mmap(addr, length, prot, flags, fd, offset);
}

int PosixFsFns::FnMsync(void *addr, size_t length, int flags) {
	return msync(addr, length, flags);
}

int PosixFsFns::FnMunmap(void *addr, size_t length) {
	return munmap(addr, length);
}

int PosixFsFns::FnFallocate(int fd, int mode, off_t offset, off_t len) {
	return fallocate(fd, mode, offset, len);
}

int PosixFsFns::FnClose(int fd) {
	return close(fd);
}

int PosixFsFns::FnRename(const string &old_path, const string &new_path) {
	return rename(old_path.c_str(), new_path.c_str());
}

int PosixFsFns::FnUnlink(const std::string &pathname) {
	return unlink(pathname.c_str());
}

int PosixFsFns::FnRemove(const std::string &pathname) {
	return remove(pathname.c_str());
}

int PosixFsFns::FnRmdir(const std::string &pathname) {
  return rmdir(pathname.c_str());
}

int PosixFsFns::FnLink(const std::string &oldpath, const std::string &newpath) {
	return link(oldpath.c_str(), newpath.c_str());
}

int PosixFsFns::FnSymlink(const std::string &oldpath, const std::string &newpath, const std::string &mnt_dir) {
	std::string new_fpath = mnt_dir + "/" + newpath;
  return symlink(oldpath.c_str(), new_fpath.c_str());
}

int PosixFsFns::FnStat(const std::string &pathname, struct stat *buf) {
	return stat(pathname.c_str(), buf);
}

bool PosixFsFns::FnPathExists(const std::string &pathname) {
  const int res = access(pathname.c_str(), F_OK);
  // TODO(ashmrtn): Should probably have some better way to handle errors.
  if (res != 0) {
    return false;
  }

  return true;
}

int PosixFsFns::FnFsync(const int fd) {
	return fsync(fd);
}

int PosixFsFns::FnFdatasync(const int fd) {
	return fdatasync(fd);
}

void PosixFsFns::FnSync() {
  sync();
}

// int PosixFsFns::FnSyncfs(const int fd) {
//   return syncfs(fd);
// }

int PosixFsFns::FnSyncFileRange(const int fd, size_t offset, size_t nbytes,
    unsigned int flags) {
  return sync_file_range(fd, offset, nbytes, flags);
}

int PosixFsFns::FnTruncate(const char *path, off_t length) {
	return truncate(path, length);
}

int PosixFsFns::FnFtruncate(const int fd, off_t length) {
	return ftruncate(fd, length);
}

int PosixFsFns::FnRead(const int fd, void* buf, size_t nbytes) {
  return read(fd, buf, nbytes);
}

/****************************************************************************/
/**************************** PassthroughCmFsOps ****************************/
/****************************************************************************/

PassthroughCmFsOps::PassthroughCmFsOps(FsFns *functions, string m) {
  fns_ = functions;
  mnt_dir = m;
}

int PassthroughCmFsOps::CmMknod(const string &pathname, const mode_t mode,
    const dev_t dev) {
  return fns_->FnMknod(pathname.c_str(), mode, dev);
}

int PassthroughCmFsOps::CmChmod(const std::string &path, mode_t mode) {
  return fns_->FnChmod(path, mode);
}

int PassthroughCmFsOps::CmMkdir(const string &pathname, const mode_t mode) {
  return fns_->FnMkdir(pathname.c_str(), mode);
}

int PassthroughCmFsOps::CmOpen(const string &pathname, const int flags) {
  return fns_->FnOpen(pathname.c_str(), flags);
}

int PassthroughCmFsOps::CmOpen(const string &pathname, const int flags,
    const mode_t mode) {
  return fns_->FnOpen2(pathname.c_str(), flags, mode);
}

off_t PassthroughCmFsOps::CmLseek(const int fd, const off_t offset,
    const int whence) {
  return fns_->FnLseek(fd, offset, whence);
}

int PassthroughCmFsOps::CmWrite(const int fd, const void *buf,
    const size_t count) {
  return fns_->FnWrite(fd, buf, count);
}

ssize_t PassthroughCmFsOps::CmPwrite(const int fd, const void *buf,
    const size_t count, const off_t offset) {
  return fns_->FnPwrite(fd, buf, count, offset);
}

void * PassthroughCmFsOps::CmMmap(void *addr, const size_t length,
    const int prot, const int flags, const int fd, const off_t offset) {
  return fns_->FnMmap(addr, length, prot, flags, fd, offset);
}

int PassthroughCmFsOps::CmMsync(void *addr, const size_t length,
    const int flags) {
  return fns_->FnMsync(addr, length, flags);
}

int PassthroughCmFsOps::CmMunmap(void *addr, const size_t length) {
  return fns_->FnMunmap(addr, length);
}

int PassthroughCmFsOps::CmFallocate(const int fd, const int mode,
    const off_t offset, off_t len) {
  return fns_->FnFallocate(fd, mode, offset, len);
}

int PassthroughCmFsOps::CmClose(const int fd) {
  return fns_->FnClose(fd);
}

int PassthroughCmFsOps::CmRename(const string &old_path,
    const string &new_path) {
  return fns_->FnRename(old_path, new_path);
}

int PassthroughCmFsOps::CmUnlink(const string &pathname) {
  return fns_->FnUnlink(pathname.c_str());
}

int PassthroughCmFsOps::CmRemove(const string &pathname) {
  return fns_->FnRemove(pathname.c_str());
}

int PassthroughCmFsOps::CmRmdir(const string &pathname) {
  return fns_->FnRmdir(pathname.c_str());
}

int PassthroughCmFsOps::CmLink(const string &oldpath, const string &newpath) {
  return fns_->FnLink(oldpath, newpath);
}

int PassthroughCmFsOps::CmSymlink(const string &oldpath, const string &newpath) {
  string relpath(newpath);
  relpath.erase(0,mnt_dir.size()+1);
  return fns_->FnSymlink(oldpath, relpath, mnt_dir);
}

int PassthroughCmFsOps::CmFsync(const int fd) {
  return fns_->FnFsync(fd);
}

int PassthroughCmFsOps::CmFdatasync(const int fd) {
  return fns_->FnFdatasync(fd);
}

void PassthroughCmFsOps::CmSync() {
  fns_->FnSync();
}

// int PassthroughCmFsOps::CmSyncfs(const int fd) {
//   return fns_->FnSyncfs(fd);
// }

int PassthroughCmFsOps::CmSyncFileRange(const int fd, size_t offset, size_t nbytes,
    unsigned int flags) {
  int ret = fns_->FnSyncFileRange(fd, offset, nbytes, flags);
  return ret;
}

int PassthroughCmFsOps::CmTruncate(const char *path, off_t length) {
  return fns_->FnTruncate(path, length);
}

int PassthroughCmFsOps::CmFtruncate(const int fd, off_t length) {
  return fns_->FnFtruncate(fd, length);
}

int PassthroughCmFsOps::CmRead(const int fd, void* buf, size_t nbytes) {
  return fns_->FnRead(fd, buf, nbytes);
}

int PassthroughCmFsOps::CmWriteData(int fd, unsigned int offset, unsigned int size) {
  // Offset into a data block to start working at.
  const unsigned int rounded_offset =
    (offset + (kTestDataSize - 1)) & (~(kTestDataSize - 1));
  // Round down size to 4k for number of full pages to write.
  
  const unsigned int aligned_size = (size >= kTestDataSize) ?
    (size - (rounded_offset - offset)) & ~(kTestDataSize - 1) :
    0;
  unsigned int num_written = 0;

  // The start of the write range is not aligned with our data blocks.
  // Therefore, we should write out part of a data block for this segment,
  // with the first character in the data block aligning with the data block
  // boundary.
  if (rounded_offset != offset) {
    // We should never write more than kTestDataSize of unaligned data at the
    // start.
    const unsigned int to_write = (size < rounded_offset - offset) ?
      size : rounded_offset - offset;
    while (num_written < to_write){
      const unsigned int mod_offset =
        (num_written + offset) & (kTestDataSize - 1);
      assert(mod_offset < kTestDataSize);

      int res = CmPwrite(fd, kTestDataBlock + mod_offset, to_write - num_written,
          offset + num_written);
      if (res < 0) {
        return res;
      }
      num_written += res;
    }
  }

  // Write out the required number of full pages for this request. The first
  // byte will be aligned with kTestDataSize.
  unsigned int aligned_written = 0;
  while (aligned_written < aligned_size) {
    const unsigned int mod_offset = (aligned_written & (kTestDataSize - 1));
    // Write up to a full page of data at a time.
    int res = CmPwrite(fd, kTestDataBlock + mod_offset,
        kTestDataSize - mod_offset, offset + num_written);
    if (res < 0) {
      return res;
    }
    num_written += res;
    aligned_written += res;
  } 

  if (num_written == size) {
    return 0;
  }

  // Write out the last partial page of data. The first byte will be aligned
  // with kTestDataSize.
  unsigned int end_written = 0;
  while (num_written < size) {
    assert(end_written < kTestDataSize);
    const unsigned int mod_offset = (end_written & (kTestDataSize - 1));
    int res = pwrite(fd, kTestDataBlock + mod_offset,
        size - num_written, offset + num_written);
    if (res < 0) {
      return res;
    }
    num_written += res;
    end_written += res;
  } 

  return 0;
}

} // api
} // user_tools
} // fs_testing
