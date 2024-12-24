#ifndef USER_TOOLS_API_WRAPPER_H
#define USER_TOOLS_API_WRAPPER_H

#include <fcntl.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <fstream>

#include <memory>
#include <string>
#include <tuple>
#include <unordered_map>
#include <vector>

#define WRAPPER_KCOV_INIT_TRACE _IOR('c', 1, unsigned long)
#define WRAPPER_KCOV_ENABLE _IO('c', 100)
#define WRAPPER_KCOV_DISABLE _IO('c', 101)
#define WRAPPER_KCOV_ENTRY_SIZE sizeof(unsigned long)
#define WRAPPER_KCOV_PATH "/sys/kernel/debug/kcov"
#define WRAPPER_KCOV_TRACE_PC 0
typedef unsigned long covert;
#define WRAPPER_COVER_SIZE (16 << 20)

namespace fs_testing {
namespace user_tools {
namespace api {

/*
 * So that things can be tested in a somewhat reasonable fashion by swapping out
 * the functions called.
 */
class FsFns {
 	public:
		virtual ~FsFns() {};
		virtual int FnMknod(const std::string &pathname, mode_t mode, dev_t dev) = 0;
		virtual int FnMkdir(const std::string &pathname, mode_t mode) = 0;
		virtual int FnOpen(const std::string &pathname, int flags) = 0;
		virtual int FnOpen2(const std::string &pathname, int flags, mode_t mode) = 0;
		virtual int FnChmod(const std::string &path, mode_t mode) = 0;
		virtual off_t FnLseek(int fd, off_t offset, int whence) = 0;
		virtual ssize_t FnWrite(int fd, const void *buf, size_t count) = 0;
		virtual ssize_t FnPwrite(int fd, const void *buf, size_t count,
			off_t offset) = 0;
		virtual void * FnMmap(void *addr, size_t length, int prot, int flags, int fd,
			off_t offset) = 0;
		virtual int FnMsync(void *addr, size_t length, int flags) = 0;
		virtual int FnMunmap(void *addr, size_t length) = 0;
		virtual int FnFallocate(int fd, int mode, off_t offset, off_t len) = 0;
		virtual int FnClose(int fd) = 0;
		virtual int FnRename(const std::string &old_path,
			const std::string &new_path) = 0;
		virtual int FnUnlink(const std::string &pathname) = 0;
		virtual int FnRemove(const std::string &pathname) = 0;
		virtual int FnRmdir(const std::string &pathname) = 0;
		virtual int FnLink(const std::string &oldpath, const std::string &newpath) = 0;
		virtual int FnSymlink(const std::string &oldpath, const std::string &newpath, const std::string &mnt_dir) = 0;

		virtual int FnStat(const std::string &pathname, struct stat *buf) = 0;
		virtual bool FnPathExists(const std::string &pathname) = 0;

		virtual int FnFsync(const int fd) = 0;
		virtual int FnFdatasync(const int fd) = 0;
		virtual void FnSync() = 0;
		// TODO(P.S.) check if we want to have syncfs
		// virtual int FnSyncfs(const int fd) = 0;
		virtual int FnSyncFileRange(const int fd, size_t offset, size_t nbytes,
			unsigned int flags) = 0;
		virtual int FnTruncate(const char* path, off_t length) = 0;
		virtual int FnFtruncate(const int fd, off_t length) = 0;
		virtual int FnRead(const int fd, void* buf, size_t nbytes) = 0;
};

class PosixFsFns : public FsFns {
 	public:
		virtual int FnMknod(const std::string &pathname, mode_t mode,
			dev_t dev) override;
		virtual int FnMkdir(const std::string &pathname, mode_t mode) override;
		virtual int FnOpen(const std::string &pathname, int flags) override;
		virtual int FnOpen2(const std::string &pathname, int flags,
			mode_t mode) override;
		virtual int FnChmod(const std::string &path, mode_t mode) override;
		virtual off_t FnLseek(int fd, off_t offset, int whence) override;
		virtual ssize_t FnWrite(int fd, const void *buf, size_t count) override;
		virtual ssize_t FnPwrite(int fd, const void *buf, size_t count,
			off_t offset) override;
		virtual void * FnMmap(void *addr, size_t length, int prot, int flags, int fd,
			off_t offset) override;
		virtual int FnMsync(void *addr, size_t length, int flags) override;
		virtual int FnMunmap(void *addr, size_t length) override;
		virtual int FnFallocate(int fd, int mode, off_t offset, off_t len) override;
		virtual int FnClose(int fd) override;
		virtual int FnRename(const std::string &old_path,
			const std::string &new_path) override;
		virtual int FnUnlink(const std::string &pathname) override;
		virtual int FnRemove(const std::string &pathname) override;
		virtual int FnRmdir(const std::string &pathname) override;
		virtual int FnLink(const std::string &oldpath, const std::string &newpath) override;
		virtual int FnSymlink(const std::string &oldpath, const std::string &newpath, const std::string &mnt_dir) override;
		
		virtual int FnStat(const std::string &pathname, struct stat *buf) override;
		virtual bool FnPathExists(const std::string &pathname) override;

		virtual int FnFsync(const int fd) override;
		virtual int FnFdatasync(const int fd) override;
		virtual void FnSync() override;
		// TODO(P.S.) check if we want to have syncfs
		// virtual int FnSyncfs(const int fd) override;
		virtual int FnSyncFileRange(const int fd, size_t offset, size_t nbytes,
			unsigned int flags) override;
		virtual int FnTruncate(const char* path, off_t length) override;
		virtual int FnFtruncate(const int fd, off_t length) override;
		virtual int FnRead(const int fd, void* buf, size_t nbytes) override;
};

class CmFsOps {
 	public:
		virtual ~CmFsOps() {};

		virtual int CmMknod(const std::string &pathname, const mode_t mode,
			const dev_t dev) = 0;
		virtual int CmMkdir(const std::string &pathname, const mode_t mode) = 0;
		virtual int CmOpen(const std::string &pathname, const int flags) = 0;
		virtual int CmOpen(const std::string &pathname, const int flags,
			const mode_t mode) = 0;
		virtual int CmChmod(const std::string &path, mode_t mode) = 0;
		virtual off_t CmLseek(const int fd, const off_t offset, const int whence) = 0;
		virtual int CmWrite(const int fd, const void *buf, const size_t count) = 0;
		virtual ssize_t CmPwrite(const int fd, const void *buf, const size_t count,
			const off_t offset) = 0;
		virtual void * CmMmap(void *addr, const size_t length, const int prot,
			const int flags, const int fd, const off_t offset) = 0;
		virtual int CmMsync(void *addr, const size_t length, const int flags) = 0;
		virtual int CmMunmap(void *addr, const size_t length) = 0;
		virtual int CmFallocate(const int fd, const int mode, const off_t offset,
			off_t len) = 0;
		virtual int CmClose(const int fd) = 0;
		virtual int CmRename(const std::string &old_path,
			const std::string &new_path) = 0;
		virtual int CmUnlink(const std::string &pathname) = 0;
		virtual int CmRemove(const std::string &pathname) = 0;
		virtual int CmRmdir(const std::string &pathname) = 0;
		virtual int CmLink(const std::string &oldpath, const std::string &newpath) = 0;
		virtual int CmSymlink(const std::string &oldpath, const std::string &newpath) = 0;

		virtual int CmFsync(const int fd) = 0;
		virtual int CmFdatasync(const int fd) = 0;
		virtual void CmSync() = 0;
		// TODO(P.S.) check if we want to have syncfs
		// virtual int CmSyncfs(const int fd) = 0;
		virtual int CmSyncFileRange(const int fd, size_t offset, size_t nbytes,
			unsigned int flags) = 0;
		virtual int CmTruncate(const char* path, off_t length) = 0;
		virtual int CmFtruncate(const int fd, off_t length) = 0;
		virtual int CmRead(const int fd, void* buf, size_t nbytes) = 0;
		virtual int CmWriteData(int fd, unsigned int offset, unsigned int size) = 0;
};

/*
 * Provides just a passthrough to the actual system calls. This is good for
 * situations where we don't want to record the individual changes a user makes
 * to the file system.
 */
class PassthroughCmFsOps : public CmFsOps {
 public:
  PassthroughCmFsOps(FsFns *functions, std::string m);
  virtual ~PassthroughCmFsOps() {};

  virtual int CmMknod(const std::string &pathname, const mode_t mode,
      const dev_t dev);
  virtual int CmMkdir(const std::string &pathname, const mode_t mode);
  virtual int CmOpen(const std::string &pathname, const int flags);
  virtual int CmOpen(const std::string &pathname, const int flags,
      const mode_t mode);
  virtual int CmChmod(const std::string &path, mode_t mode);
  virtual off_t CmLseek(const int fd, const off_t offset, const int whence);
  virtual int CmWrite(const int fd, const void *buf, const size_t count);
  virtual ssize_t CmPwrite(const int fd, const void *buf, const size_t count,
      const off_t offset);
  virtual void * CmMmap(void *addr, const size_t length, const int prot,
      const int flags, const int fd, const off_t offset);
  virtual int CmMsync(void *addr, const size_t length, const int flags);
  virtual int CmMunmap(void *addr, const size_t length);
  virtual int CmFallocate(const int fd, const int mode, const off_t offset,
      off_t len);
  virtual int CmClose(const int fd);
  virtual int CmRename(const std::string &old_path,
      const std::string &new_path);
  virtual int CmUnlink(const std::string &pathname);
  virtual int CmRemove(const std::string &pathname);
  virtual int CmRmdir(const std::string &pathname);
  virtual int CmLink(const std::string &oldpath, const std::string &newpath);
  virtual int CmSymlink(const std::string &oldpath, const std::string &newpath);

  virtual int CmFsync(const int fd);
  virtual int CmFdatasync(const int fd);
  virtual void CmSync();
  // TODO(P.S.) check if we want to have syncfs
  // virtual int CmSyncfs(const int fd);
  virtual int CmSyncFileRange(const int fd, size_t offset, size_t nbytes,
    unsigned int flags);
  virtual int CmTruncate(const char *path, off_t length);
  virtual int CmFtruncate(const int fd, off_t length);
  virtual int CmRead(const int fd, void* buf, size_t nbytes);
  virtual int CmWriteData(int fd, unsigned int offset, unsigned int size);

 protected:
  // Set of functions to call for different file system operations. Tracked as a
  // set of function pointers so that this class can be tested in a somewhat
  // sane manner.
  FsFns *fns_;
  std::string mnt_dir;
};

} // api
} // user_tools
} // fs_testing

#endif // USER_TOOLS_API_WRAPPER_H
