// #define __KERNEL__ 1

#include <linux/fcntl.h>
#include <linux/file.h>
#include <linux/fs.h>
#include <linux/hashtable.h>
#include <linux/list.h>
#include <linux/mutex.h>
#include <linux/preempt.h>
#include <linux/printk.h>
#include <linux/syscalls.h>
#include <linux/types.h>

#ifdef pr_fmt
#undef pr_fmt
#define pr_fmt(fmt) "nova-trace: " fmt
#endif

// #define inj_trace_err(fmt, args...)
#define inj_trace_err(fmt, args...) pr_err(fmt, ##args)
// #define inj_trace_info(fmt, args...)
#define inj_trace_info(fmt, args...) pr_info(fmt, ##args)
// #define wr_filename "/tmp/nova.inject.func.trace"
// #define sv_filename "/tmp/nova.inject.storevalue.trace"
#define wr_filename "/mnt/ramfs/nova.inject.func.trace"
#define sv_filename "/mnt/ramfs/nova.inject.storevalue.trace"
#define MAX_SV_BUF_SIZE 104857600
#define MAX_UINT64_NUM (~0ULL)

static DEFINE_SPINLOCK(trace_lock);
static DEFINE_SPINLOCK(offset_lock);
static DEFINE_SPINLOCK(sv_offset_lock);
static struct file *filp = NULL;
static struct file *sv_filp = NULL;
static loff_t offset = 0;
static loff_t sv_offset = 0;
static void *nvmm_virt_start_addr = 0;
static void *nvmm_virt_end_addr = 0;
static long nvmm_virt_size = 0;
static int trace_enabled = 0;
static u64 trace_order_num = 1;

/*********************************** mutex ***********************************/
#define offset_lock_lock()                                                      \
  do {                                                                         \
    spin_lock(&offset_lock);                                                    \
  } while (0)

#define offset_lock_unlock()                                                    \
  do {                                                                         \
    spin_unlock(&offset_lock);                                                  \
  } while (0)

#define sv_offset_lock_lock()                                                      \
  do {                                                                         \
    spin_lock(&sv_offset_lock);                                                    \
  } while (0)

#define sv_offset_lock_unlock()                                                    \
  do {                                                                         \
    spin_unlock(&sv_offset_lock);                                                  \
  } while (0)

#define trace_lock_lock()                                                      \
  do {                                                                         \
    spin_lock(&trace_lock);                                                    \
  } while (0)

#define trace_lock_unlock()                                                    \
  do {                                                                         \
    spin_unlock(&trace_lock);                                                  \
  } while (0)


/*********************************** utils ***********************************/
static int get_current_pid(void) { return current->pid; }

#define TRACE_DRAM_ADDR true

// return true if the address is in NVMM space.
static bool check_dest_addr_nvmm(void *ptr, uint64_t size) {
  // giri analyze all memory access, no matter DRAM or PM.
  if (nvmm_virt_start_addr > 0 && ptr >= nvmm_virt_start_addr &&
      ptr + size <= nvmm_virt_end_addr) {
    return true;
  } else {
    return false;
  }
}

static bool is_user_space_address(void *addr) {
  // https://linux-kernel-labs.github.io/refs/heads/master/lectures/address-space.html#linux-address-space
  // https://www.kernel.org/doc/html/latest/x86/x86_64/mm.html
  if ((u64)addr < 0x8000000000000000) {
    return true;
  } else {
    return false;
  }
}

/******************************** output file ********************************/
static void open_file(void) {
  mm_segment_t old_fs = get_fs();
  int err = 0;

  if (filp != NULL) {
    return;
  }

  set_fs(KERNEL_DS);

  filp = filp_open(wr_filename, O_WRONLY | O_CREAT | O_TRUNC, 0666);
  if (filp == NULL) {
    err = PTR_ERR(filp);
    inj_trace_err("open file failed, errcode: %d\n", err);
  }
  set_fs(old_fs);
}

static void close_file(void) {
  mm_segment_t old_fs = get_fs();

  if (filp == NULL) {
    return;
  }

  set_fs(KERNEL_DS);
  if (filp) {
    filp_close(filp, NULL);
    filp = NULL;
  }
  set_fs(old_fs);
}

static void write_file(char *data, size_t len) {
  loff_t off = 0;
  ssize_t wb = 0;
  mm_segment_t old_fs = get_fs();

  offset_lock_lock();
  off = offset;
  offset += len;
  offset_lock_unlock();

  set_fs(KERNEL_DS);
  if (filp) {
    wb = kernel_write(filp, data, len, &off);
    if (wb != len) {
      inj_trace_err("expect to write %u bytes, but written %d bytes\n", len, wb);
    }
  }
  set_fs(old_fs);
}

/************************** output store value file **************************/
static void open_sv_file(void) {
  mm_segment_t old_fs = get_fs();
  int err = 0;

  if (sv_filp != NULL) {
    return;
  }

  set_fs(KERNEL_DS);

  sv_filp = filp_open(sv_filename, O_WRONLY | O_CREAT | O_TRUNC, 0666);
  if (sv_filp == NULL) {
    err = PTR_ERR(sv_filp);
    inj_trace_err("open file failed, errcode: %d\n", err);
  }
  set_fs(old_fs);
}

static void close_sv_file(void) {
  mm_segment_t old_fs = get_fs();

  if (sv_filp == NULL) {
    return;
  }

  set_fs(KERNEL_DS);
  if (sv_filp) {
    filp_close(sv_filp, NULL);
    filp = NULL;
  }
  set_fs(old_fs);
}

static void write_sv_file(uint64_t seq, char *data, uint64_t len) {
  loff_t start_off = 0, off = 0;
  ssize_t wb = 0;
  mm_segment_t old_fs = get_fs();

  if (len > MAX_SV_BUF_SIZE) {
    inj_trace_info("bug is too large, %llu!\n", len);
    return ;
  }

  sv_offset_lock_lock();
  start_off = sv_offset;
  sv_offset += sizeof(uint64_t) + sizeof(uint64_t) + len;
  sv_offset_lock_unlock();

  set_fs(KERNEL_DS);
  if (sv_filp) {
    off = start_off;
    wb = kernel_write(sv_filp, (void*) &seq, sizeof(uint64_t), &off);
    if (wb != sizeof(uint64_t)) {
      inj_trace_err("expect to write %u bytes, but written %d bytes\n", sizeof(uint64_t), wb);
    }
    off = start_off + sizeof(uint64_t);
    wb = kernel_write(sv_filp, (void*) &len, sizeof(uint64_t), &off);
    if (wb != sizeof(uint64_t)) {
      inj_trace_err("expect to write %u bytes, but written %d bytes\n", sizeof(uint64_t), wb);
    }
    off = start_off + sizeof(uint64_t) + sizeof(uint64_t);
    wb = kernel_write(sv_filp, data, len, &off);
    if (wb != len) {
      inj_trace_err("expect to write %u bytes, but written %d bytes\n", len, wb);
    }
  }
  set_fs(old_fs);
}

/******************************** write buffer ********************************/
static LIST_HEAD(trace_wbuf_header);
static u32 trace_num_wbuf = 0;

struct trace_wbuf_t {
  size_t size;
  char *buf;
  struct list_head list;
};

static struct kmem_cache *trace_wbuf_cachep;

static void create_trace_wbuf_cache(void) {
  if (trace_wbuf_cachep != NULL) {
    return;
  }

  trace_wbuf_cachep = kmem_cache_create(
      "trace_wbuf", sizeof(struct trace_wbuf_t), 0, SLAB_RECLAIM_ACCOUNT, NULL);
}

static void destroy_trace_wbuf_cache(void) {
  if (trace_wbuf_cachep) {
    kmem_cache_destroy(trace_wbuf_cachep);
    trace_wbuf_cachep = NULL;
  }
}

static struct trace_wbuf_t *new_trace_wbuf_node(void) {
  struct trace_wbuf_t *node = NULL;

  if (trace_wbuf_cachep != NULL)
    node = (struct trace_wbuf_t *)kmem_cache_alloc(trace_wbuf_cachep, GFP_ATOMIC);

  return node;
}

static void free_trace_wbuf_node(struct trace_wbuf_t *node) {
  if (node)
    kmem_cache_free(trace_wbuf_cachep, node);
}

static void trace_wbuf_add(char *src, size_t size) {
  struct trace_wbuf_t *node;
  if (size > 512) {
    size = 512;
  }

  node = new_trace_wbuf_node();
  if (node == NULL) {
    inj_trace_err("Node is NULL!\n");
    return;
  }

  node->buf = kmalloc(size, GFP_ATOMIC);
  if (node->buf == NULL) {
    inj_trace_err("kmalloc is NULL!\n");
    kmem_cache_free(trace_wbuf_cachep, node);
    return;
  }

  memcpy(node->buf, src, size);
  node->size = size;

  trace_lock_lock();
  ++trace_num_wbuf;
  list_add_tail(&node->list, &trace_wbuf_header);
  trace_lock_unlock();
}

static void trace_wbuf_write_all(bool is_locked) {
  struct trace_wbuf_t *pos, *n;

  if (list_empty(&trace_wbuf_header)) {
    return;
  }

  // this function is only called when no-atomic content.
  // Safe to lock it.
  if (!is_locked)
    trace_lock_lock();

  inj_trace_info("clear wbuf: trace_num_wbuf: %u\n", trace_num_wbuf);
  list_for_each_entry_safe(pos, n, &trace_wbuf_header, list) {
    if (pos->buf) {
      write_file(pos->buf, pos->size);
      kfree(pos->buf);
    }
    --trace_num_wbuf;
    list_del(&pos->list);
    free_trace_wbuf_node(pos);
  }
  inj_trace_info("clear wbuf done: trace_num_wbuf: %u\n", trace_num_wbuf);

  if (!is_locked)
    trace_lock_unlock();
}

/*************************** save value file buffer ***************************/
static LIST_HEAD(trace_svbuf_header);
static u32 trace_num_svbuf = 0;

struct trace_svbuf_t {
  uint64_t seq; // the id of the corresponding sequence number.
  uint64_t size;
  char *buf;
  struct list_head list;
};

static struct kmem_cache *trace_svbuf_cachep;

static void create_trace_svbuf_cache(void) {
  if (trace_svbuf_cachep != NULL) {
    return;
  }

  trace_svbuf_cachep = kmem_cache_create(
      "trace_svbuf", sizeof(struct trace_svbuf_t), 0, SLAB_RECLAIM_ACCOUNT, NULL);
}

static void destroy_trace_svbuf_cache(void) {
  if (trace_svbuf_cachep) {
    kmem_cache_destroy(trace_svbuf_cachep);
    trace_svbuf_cachep = NULL;
  }
}

static struct trace_svbuf_t *new_trace_svbuf_node(void) {
  struct trace_svbuf_t *node = NULL;

  if (trace_svbuf_cachep != NULL)
    node = (struct trace_svbuf_t *)kmem_cache_alloc(trace_svbuf_cachep, GFP_ATOMIC);

  return node;
}

static void free_trace_svbuf_node(struct trace_svbuf_t *node) {
  if (node)
    kmem_cache_free(trace_svbuf_cachep, node);
}

static void trace_svbuf_add(uint64_t seq, char *src, uint64_t size) {
  struct trace_svbuf_t *node;
  if (size > MAX_SV_BUF_SIZE) {
    inj_trace_info("bug is too large, %llu!\n", size);
    return ;
  }

  node = new_trace_svbuf_node();
  if (node == NULL) {
    inj_trace_err("Node is NULL!\n");
    return;
  }

  node->buf = kmalloc(size, GFP_ATOMIC);
  if (node->buf == NULL) {
    inj_trace_err("kmalloc is NULL!\n");
    kmem_cache_free(trace_svbuf_cachep, node);
    return;
  }

  memcpy(node->buf, src, size);
  node->seq = seq;
  node->size = size;

  trace_lock_lock();
  ++trace_num_svbuf;
  list_add_tail(&node->list, &trace_svbuf_header);
  trace_lock_unlock();
}

static void trace_svbuf_write_all(bool is_locked) {
  struct trace_svbuf_t *pos, *n;

  if (list_empty(&trace_svbuf_header)) {
    return;
  }

  // this function is only called in no-atomic content.
  // Safe to lock it.
  if (!is_locked)
    trace_lock_lock();

  inj_trace_info("clear svbuf: trace_num_svbuf: %u\n", trace_num_svbuf);
  list_for_each_entry_safe(pos, n, &trace_svbuf_header, list) {
    if (pos->buf) {
      write_sv_file(pos->seq, pos->buf, pos->size);
      kfree(pos->buf);
    }
    --trace_num_svbuf;
    list_del(&pos->list);
    free_trace_svbuf_node(pos);
  }
  inj_trace_info("clear svbuf done: trace_num_svbuf: %u\n", trace_num_svbuf);

  if (!is_locked)
    trace_lock_unlock();
}

/*************************** trace debug info of IR ***************************/
#define DEBUG_TRACE()
#define DEBUG_INFO(...)
#define DEBUG_MSG(...)

#ifdef TRACE_OUTPUT_DEBUG_INFO
#define OUTPUT_DBG_INFO(line, col, fname, code)                                \
  do {                                                                         \
    if (fname && code) {                                                       \
      output_record(seq, "\t\tfile: %s, line %u, col: %u, code: %s.\n",             \
                    (char *)fname, line, col, (char *)code);                   \
    } else if (fname) {                                                        \
      output_record(seq, "\t\tfile: %s, line %u, col: %u, code: NULL.\n",           \
                    (char *)fname, line, col);                                 \
    } else {                                                                   \
      output_record(seq, "\t\tfile: NULL, line %u, col: %u, code: NULL.\n", line,   \
                    col);                                                      \
    }                                                                          \
  } while (0)
#else
#define OUTPUT_DBG_INFO(line, col, fname, code)
#endif


/********************************* output msg *********************************/
static void output_open_file(void) { open_file(); open_sv_file(); }

static void output_close_file(void) { close_file(); close_sv_file(); }

static void output_record(uint64_t seq, const char *fmt, ...) {
  size_t size1, size2;
  char buf[512];
  va_list args;

  size1 = snprintf(buf, 512, "%8lu, %8d, ", seq, get_current_pid());

  va_start(args, fmt);
  size2 = vsnprintf(buf + size1, 512 - size1, fmt, args);
  va_end(args);

  if (size1 + size2 == 512) {
    buf[511] = '\n';
  }

  trace_wbuf_add(buf, size1 + size2);
  return ;

  // do not why the below code does not work when tracing pmfs.
  if (in_irq() || in_softirq() || in_interrupt() || in_nmi() || in_atomic()
  ||
      in_atomic_preempt_off()) {
    trace_wbuf_add(buf, size1 + size2);
  } else {
    trace_wbuf_write_all(false);
    write_file(buf, size1 + size2);
  }
}

static void output_store_value(uint64_t seq, char *buf, uint64_t len) {
  trace_svbuf_add(seq, buf, len);
  return ;

  // do not why the below code does not work when tracing pmfs.
  if (in_irq() || in_softirq() || in_interrupt() || in_nmi() || in_atomic()
  ||
      in_atomic_preempt_off()) {
    trace_svbuf_add(seq, buf, len);
  } else {
    trace_svbuf_write_all(false);
    write_sv_file(seq, buf, len);
  }
}

// #define output_record(fmt, ...)                                            \
//   do {                                                                         \
//     size_t size;                                                               \
//     char buf[512];                                                             \
//     size = snprintf(buf, 512, "%8lu, %8d, " fmt, trace_order_num,              \
//                     get_current_pid(), ##__VA_ARGS__);                                  \
//     if (size == 512) {                                                         \
//       buf[511] = '\n';                                                         \
//     }                                                                          \
//     if (in_irq() || in_softirq() || in_interrupt() || in_nmi() ||              \
//         in_atomic() || in_atomic_preempt_off()) {                              \
//       trace_wbuf_add(buf, size);                                               \
//     } else {                                                                   \
//       trace_wbuf_write_all();                                                  \
//       write_file(buf, size);                                                   \
//     }                                                                          \
//   } while (0)

/******************************************************************************/
/****************************** trace functions ******************************/
/******************************************************************************/

/************************************ init ************************************/
void trace_init_all(void) {
  trace_lock_lock();

  if (trace_enabled != 0) {
    inj_trace_info("init trace is enabled.\n");
    goto done;
  }

  inj_trace_info("start init\n");

  create_trace_wbuf_cache();
  create_trace_svbuf_cache();

  if (trace_wbuf_cachep == NULL) {
    trace_enabled = -1;
  }

  // open user space file.
  output_open_file();

  // set the flag to enable the trace.
  offset = 0;
  nvmm_virt_start_addr = 0;
  nvmm_virt_end_addr = 0;
  nvmm_virt_size = 0;
  trace_order_num = 1;
  trace_enabled = 1;

  if (filp == NULL || sv_filp == NULL) {
    trace_enabled = -1;
    inj_trace_err("filp is NULL after open!\n");
  }

  inj_trace_info("init is done.\n");

done:
  trace_lock_unlock();
}

void trace_destroy_all(int init_fs_ret_val) {
  trace_lock_lock();

  if (init_fs_ret_val == 0) {
    inj_trace_info("no exit.\n");
    goto done;
  }

  if (trace_enabled == 0) {
    inj_trace_info("exit trace is not enabled.\n");
    goto done;
  } // if it is -1, we still need to clear the resource.

  inj_trace_info("exit is going...\n");
  // write all data to user space before exit the module.
  trace_wbuf_write_all(true);
  trace_svbuf_write_all(true);

  offset = 0;
  nvmm_virt_start_addr = 0;
  nvmm_virt_end_addr = 0;
  nvmm_virt_size = 0;
  trace_enabled = 0;

  destroy_trace_svbuf_cache();
  destroy_trace_wbuf_cache();

  output_close_file();
  inj_trace_info("exit is done.\n");

done:
  trace_lock_unlock();
}

/***************************** tracking sequence *****************************/
#define TRACE_UNLOCK_OR_RETURN(incby)                                          \
  do {                                                                         \
    if (trace_enabled == 0) {                                                  \
      trace_lock_unlock();                                                     \
      return;                                                                  \
    }                                                                          \
    seq = trace_order_num;                                                     \
    trace_order_num += incby;                                                  \
    trace_lock_unlock();                                                       \
  } while (0)

#define MAX_TRACE_SEQ_NUM  2000000000000ULL

#define TRACE_CHECK_SEQ_RETURN(seq)                                            \
  if (seq >= MAX_TRACE_SEQ_NUM) {                                              \
    return;                                                                    \
  }

uint64_t trace_acquire_sequence(uint64_t incby) {
  uint64_t seq = MAX_TRACE_SEQ_NUM;
  trace_lock_lock();
  if (trace_enabled != 0) {
    seq = trace_order_num;
    trace_order_num += incby;
  }
  trace_lock_unlock();
  return seq;
}

/*************************** tracking of old value ***************************/
// one trillion, used to identify new stored value and old stored value
#define OLDSV_START_SEQ  1000000000000ULL

void trace_old_store_value(uint64_t seq, void *ptr, uint64_t size, uint64_t shift) {
  TRACE_CHECK_SEQ_RETURN(seq);

  if (is_user_space_address(ptr)) {
    // we cannot access the user space data.
    return ;
  }

  // shift is used to get the correct seq number of store instruction in uaccess, memcpy, etc..
  seq += shift;
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    seq += OLDSV_START_SEQ;
    DEBUG_INFO("seq: %llu, ptr: 0x%p, size: %8llu.\n", seq, ptr, size);
    output_store_value(seq, ptr, size);
  }
}

/********************************* inline asm *********************************/
void trace_inline_asm_flush(uint32_t id, void *src) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(src, 64)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p.\n", id, src);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx.\n", "asmFlush", id,
                  (unsigned long)src);
  }
}

void trace_inline_asm_fence(uint32_t id) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  DEBUG_INFO("id: %u.\n", id);
  output_record(seq, "%-15s, id: %8u.\n", "asmFence", id);
}

void trace_implicit_fence(uint32_t id) {
  // including CAS, interrupts, lock, XChg, etc.
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  DEBUG_INFO("id: %u.\n", id);
  output_record(seq, "%-15s, id: %8u.\n", "impFence", id);
}

void trace_inline_asm_xchglq(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "asmxchg", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

void trace_inline_asm_cas(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "cas", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

void trace_inline_asm_memsetnt(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "asmmemsetnt",
                  id, (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

void trace_inline_asm_unknown(uint32_t id, char *caller_name, char *fname,
                              uint32_t line, char *asm_str) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  DEBUG_INFO("id: %8u, asm: %s.\n", id, asm_str);
  if (strlen(asm_str) < 400)
    output_record(seq, "%-15s, id: %8u, caller: %s, fname: %s, line: %u, asm: %s.\n",
                  "ukasm", id, caller_name, fname, line, asm_str);
  else
    output_record(seq, "%-15s, id: %8u, caller: %s, fname: %s, line: %u, asm: %s.\n",
                  "ukasm", id, caller_name, fname, line, "TooLong");
}

/*********************** tracking of other instructions ***********************/
void trace_start_func(uint32_t id, void *func_ptr, char *func_name) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, fn: %s.\n", "startFunc", id,
                (u64)func_ptr, func_name);
}

void trace_end_func(uint32_t id, void *func_ptr, char *func_name) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, fn: %s.\n", "endFunc", id,
                (u64)func_ptr, func_name);
}

void trace_start_bb(uint32_t id, void *func_ptr, char *func_name) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, fn: %s.\n", "startBB", id,
                (unsigned long)func_ptr, func_name);
}

void trace_end_bb(uint32_t id, void *func_ptr, char *func_name, uint32_t lastBB) {
  uint64_t seq = 0;
  int call_id = 0;

  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);

  output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, fn: %s, call_id: %8lu.\n", "endBB", id,
                (uint64_t)func_ptr, func_name, call_id);
}

/*************** visit memory access and addressing operations ***************/
void trace_load_inst(uint32_t id, void *ptr, uint64_t size, int line, int col,
                     void *fname, void *code) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    // DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "load", id,
                  (unsigned long)ptr, size);
    OUTPUT_DBG_INFO(line, col, fname, code);
  }
}

void trace_store_inst(uint64_t seq, uint32_t id, void *ptr, uint64_t size, int line, int col,
                      void *fname, void *code) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "store", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
    OUTPUT_DBG_INFO(line, col, fname, code);
  }
}

void trace_fence_inst(uint32_t id, int line, int col, void *fname, void *code) {
  return trace_inline_asm_fence(id);

  // uint64_t seq = 0;
  // trace_lock_lock();
  // TRACE_UNLOCK_OR_RETURN(1);
  // DEBUG_INFO("id: %u.\n", id);
  // output_record(seq, "%-15s, id: %8u.\n", "fence", id);
  // OUTPUT_DBG_INFO(line, col, fname, code);
}

void trace_xchg_inst(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "xchg", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

void trace_rmw_inst(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "rmw", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

/************************ memory intrinsic instructions ***********************/
void trace_memset_inst(uint64_t seq, uint32_t id, void *ptr, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "memset", id,
                  (unsigned long)ptr, size);
    output_store_value(seq, ptr, size);
  }
}

void trace_memtransfer_inst(uint64_t seq, uint32_t id, void *dest, void *src, uint64_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  DEBUG_INFO("id: %8u, src: 0x%p, dest: 0x%p, size: %8llu.\n", id, src, dest,
             size);

  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(src, size)) {
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "memtransLoad",
                  id, (unsigned long)src, size);
  }
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(dest, size)) {
    output_record(seq + 1, "%-15s, id: %8u, ptr: 0x%lx, size: %8llu.\n", "memtransStore",
                  id, (unsigned long)dest, size);
    output_store_value(seq + 1, dest, size);
  }
}

/****************************** branches related ******************************/
void trace_select_inst(uint32_t id, u64 flag) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(
      seq, "%-15s, id: %8u, flag: %lu.\n", "select", id, flag);
}

/******************************* function calls *******************************/
void trace_start_calls(uint32_t id, char *caller_name,
                         char *callee_name, char *fname, uint32_t line) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(seq,
      "%-15s, id: %8u, caller: %s, callee: %s, fname: %s, line: %u.\n",
      "startCall", id, caller_name, callee_name, fname, line);
}

void trace_end_calls(uint32_t id, char *caller_name,
                         char *callee_name, char *fname, uint32_t line) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  output_record(seq,
      "%-15s, id: %8u, caller: %s, callee: %s, fname: %s, line: %u.\n",
      "endCall", id, caller_name, callee_name, fname, line);
}

void trace_uaccess_calls(uint64_t seq, uint32_t id, void *to, void *from,
                         unsigned long size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (is_user_space_address(to)) {
    // we do not trace the data copied to the user space.
    return ;
  }

  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(from, size)) {
    output_record(seq, "%-15s, id: %8u, from: 0x%lx, to: 0x%lx, size: %8llu.\n",
                  "uaccessLoad", id, (unsigned long)from, (unsigned long)to,
                  size);
  }
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(to, size)) {
    output_record(seq + 1, "%-15s, id: %8u, from: 0x%lx, to: 0x%lx, size: %8llu.\n",
                  "uaccessStore", id, (unsigned long)from, (unsigned long)to,
                  size);
    output_store_value(seq + 1, to, size);
  }
}

void trace_uaccess_nt_calls(uint64_t seq, uint32_t id, void *to, void *from,
                         unsigned long size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (is_user_space_address(to)) {
    // we do not trace the data copied to the user space.
    return ;
  }

  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(from, size)) {
    output_record(seq, "%-15s, id: %8u, from: 0x%lx, to: 0x%lx, size: %8llu.\n",
                  "uaccessNTLoad", id, (unsigned long)from, (unsigned long)to,
                  size);
  }
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(to, size)) {
    output_record(seq + 1, "%-15s, id: %8u, from: 0x%lx, to: 0x%lx, size: %8llu.\n",
                  "uaccessNTStore", id, (unsigned long)from, (unsigned long)to,
                  size);
    output_store_value(seq + 1, to, size);
  }
}

/********************** centeralized flush function call **********************/
void trace_centralized_flush(uint64_t seq, uint32_t id, void *ptr, uint32_t size) {
  TRACE_CHECK_SEQ_RETURN(seq);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, ptr: 0x%lx, size: %8u.\n", "centflush", id,
                  (unsigned long)ptr, size);
  }
}

/************************** other special functions **************************/
void trace_dax_access(uint32_t id, void **addr, long size) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);

  DEBUG_INFO("id: %8u, addr: %p.\n", id, addr);
  nvmm_virt_start_addr = (*addr);
  nvmm_virt_size = (size * 4096);
  nvmm_virt_end_addr = nvmm_virt_start_addr + nvmm_virt_size;
  inj_trace_info("id: %8u, addr: 0x%lx - 0x%lx, size: %ld.\n", id,
                 (unsigned long)nvmm_virt_start_addr,
                 (unsigned long)nvmm_virt_end_addr, nvmm_virt_size);
  output_record(seq, "%-15s, id: %8u, 0x%lx, 0x%lx, %ld.\n", "DaxDevInfo", 0, nvmm_virt_start_addr, nvmm_virt_end_addr, nvmm_virt_size/1048576);
}

/****************************** data structures ******************************/
void trace_pm_struct_ptr_inst(uint32_t id, void *ptr, uint32_t idx, uint64_t size,
                              char *stname, int line, int col, void *fname,
                              void *code) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  // DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
  if (TRACE_DRAM_ADDR || check_dest_addr_nvmm(ptr, size)) {
    output_record(seq, "%-15s, id: %8u, type: %-15s, ptr: 0x%lx, idx: %4u, size: %8llu.\n",
                  "PMStructPtr", id, stname, (unsigned long)ptr, idx, size);
    OUTPUT_DBG_INFO(line, col, fname, code);
  }
}

void trace_dram_struct_ptr_inst(uint32_t id, void *ptr, uint32_t idx, uint64_t size,
                                char *stname, int line, int col, void *fname,
                                void *code) {
  // since this is dram struct pointers, it will failed for the check,
  // thus, we just disable it here.
  // if (!check_dest_addr_nvmm(ptr, size))
  //     return ;
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  // DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
  output_record(seq, "%-15s, id: %8u, type: %-15s, ptr: 0x%lx, idx: %4u, size: %8llu.\n",
                "DRAMStructPtr", id, stname, (unsigned long)ptr, idx, size);
  OUTPUT_DBG_INFO(line, col, fname, code);
}

void trace_unknown_struct_ptr_inst(uint32_t id, void *ptr, uint32_t idx, uint64_t size,
                              char *stname, int line, int col, void *fname,
                              void *code) {
  uint64_t seq = 0;

  if (nvmm_virt_start_addr != 0 && nvmm_virt_end_addr != 0 && nvmm_virt_size != 0) {
    trace_lock_lock();
    TRACE_UNLOCK_OR_RETURN(1);
    // DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
    output_record(seq, "%-15s, id: %8u, type: %-15s, ptr: 0x%lx, idx: %4u, size: %8llu.\n",
                  "UKStructPtr", id, stname, (unsigned long)ptr, idx, size);
    OUTPUT_DBG_INFO(line, col, fname, code);
  } else {
    if (check_dest_addr_nvmm(ptr, size)) {
      trace_pm_struct_ptr_inst(id, ptr, idx, size, stname, line, col, fname, code);
    } else {
      trace_dram_struct_ptr_inst(id, ptr, idx, size, stname, line, col, fname, code);
    }
  }
}

/****************************** visit dbg calls ******************************/
void trace_dbg_var_store(uint32_t id, void *ptr, char *stname, uint64_t size) {
  uint64_t seq = 0;
  trace_lock_lock();
  TRACE_UNLOCK_OR_RETURN(1);
  // DEBUG_INFO("id: %8u, ptr: 0x%p, size: %8llu.\n", id, ptr, size);
  output_record(seq, "%-15s, id: %8u, type: %-15s, ptr: 0x%lx, size: %8llu.\n",
                "dbgStore", id, stname, (unsigned long)ptr, size);
}