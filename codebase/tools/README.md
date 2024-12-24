## Tools
This directory houses several standalone tools.

#### Files
|- disk_content: exported from CrashMonkey for obtaining attrs of files and dirs recursively
|- md5: a C++ written MD5 library
|- scripts: some scripts that used to read the dumped files from src_info and struct_layout_ast
|- src_info: used to get function and structure lists from source code
|- struct_layout_ast: used to get structure layout from source code according to the structure names that obtained from src_info
|- struct_layout_pass: similar to struct_layout_ast, but implemented by using LLVM pass

#### disk_content
Using the `stat` function to get disk content of a specified path. The file `DumpDiskContent.cpp` can dump the disk content to a separate file for later use.

#### src_info
This tool leverages Clang tools to obtain functions of POSIX operations and structures in source files. We do not differentiate between persistent structures and temporary (DRAM) structures in this work, which is carried out by analyzing the execution trace.

How to use the tool to dump such information to a file:
```shell
# example 1
# DumpSrcInfo.cpp is the target passed to LLVM
# The real parsed files are specific by src_dir
# Use src_files "file1 file2" to specific certain files if does not want to
# parse all files in a directory.
./DumpSrcInfo --output_posix_func_fname xx.1 \
    --output_all_func_fname xx.2 \
    --output_struct_fname xx.3 \
    --src_dir ./ \
    DumpSrcInfo.cpp -- -x c++

# example 2
cd /path/to/nova/src/code
TMP_KERNEL_INC=/usr/src/linux-headers-5.4.0-131-generic && \
TMP_CLANG_INC=/home/bing/usr/local/llvm-15.0.1/rel/lib/clang/15.0.1/include && \
TMP_SRC_FILE="*.c" && \
TMP_SRC_DIR="./" && \
TMP_SRC_FILES="nova.h inode.h" && \
TMP_BASE_SRC_NAME=na && \
TMP_MODULE_NAME=na && \
TMP_OUTPUT_VFS_FUNC_NAME=xx.posix.func.info && \
TMP_OUTPUT_ALL_FUNC_NAME=xx.func.info && \
TMP_OUTPUT_STRUCT_NAME=xx.struct.info && \
~/Silhouette/codebase/tools/src_info/DumpSrcInfo \
    --output_vfs_func_fname=$TMP_OUTPUT_VFS_FUNC_NAME \
    --output_all_func_fname=$TMP_OUTPUT_ALL_FUNC_NAME \
    --output_struct_fname=$TMP_OUTPUT_STRUCT_NAME \
    --src_dir=$TMP_SRC_DIR \
    --src_files=$TMP_SRC_FILES \
    $TMP_SRC_FILE \
    -- -x c \
    -nostdinc \
    -isystem $TMP_CLANG_INC \
    -I $TMP_KERNEL_INC/arch/x86/include \
    -I $TMP_KERNEL_INC/arch/x86/include/generated  \
    -I $TMP_KERNEL_INC/include \
    -I $TMP_KERNEL_INC/arch/x86/include/uapi \
    -I $TMP_KERNEL_INC/arch/x86/include/generated/uapi \
    -I $TMP_KERNEL_INC/include/uapi \
    -I $TMP_KERNEL_INC/include/generated/uapi \
    -include  $TMP_KERNEL_INC/include/linux/kconfig.h \
    -include  $TMP_KERNEL_INC/include/linux/compiler_types.h \
    -D__KERNEL__ \
    -Qunused-arguments -Wall -Wundef -Werror=strict-prototypes \
    -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar \
    -fno-PIE -Werror=implicit-function-declaration -Werror=implicit-int \
    -Wno-format-security -std=gnu89 -no-integrated-as -mno-sse -mno-mmx \
    -mno-sse2 -mno-3dnow -mno-avx -m64 -falign-loops=1 -mno-80387 \
    -mno-fp-ret-in-387 -mstack-alignment=8 -mskip-rax-setup \
    -mtune=generic -mno-red-zone -mcmodel=kernel -DCONFIG_X86_X32_ABI \
    -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 \
    -DCONFIG_AS_SSSE3=1 -DCONFIG_AS_AVX=1 -DCONFIG_AS_AVX2=1 \
    -DCONFIG_AS_AVX512=1 -DCONFIG_AS_SHA1_NI=1 -DCONFIG_AS_SHA256_NI=1 \
    -Wno-sign-compare -fno-asynchronous-unwind-tables \
    -mretpoline-external-thunk -fno-delete-null-pointer-checks \
    -Wno-frame-address -Wno-int-in-bool-context -Wno-address-of-packed-member \
    -O2 -Wframe-larger-than=1024 -fstack-protector-strong \
    -Wno-format-invalid-specifier -Wno-gnu -Wno-tautological-compare \
    -mno-global-merge -Wno-unused-const-variable -fno-omit-frame-pointer \
    -fno-optimize-sibling-calls -g -gdwarf-4 -pg -mfentry -DCC_USING_FENTRY \
    -Wdeclaration-after-statement -Wvla -Wno-pointer-sign -fno-strict-overflow \
    -fno-merge-all-constants -fno-stack-check -Werror=date-time \
    -Werror=incompatible-pointer-types \
    -fmacro-prefix-map=./= -Wno-initializer-overrides -Wno-unused-value \
    -Wno-format -Wno-sign-compare -Wno-format-zero-length \
    -Wno-uninitialized -fno-pic -fno-pie -fsanitize=kernel-address \
    -mllvm -asan-mapping-offset=0xdffffc0000000000  -mllvm -asan-globals=1 \
    -mllvm -asan-instrumentation-with-call-threshold=0  -mllvm -asan-stack=1 \
    --param asan-instrument-allocas=1 -fsanitize=shift \
    -fsanitize=integer-divide-by-zero  -fsanitize=unreachable \
    -fsanitize=vla-bound -fsanitize=signed-integer-overflow -fsanitize=bounds \
    -fsanitize=object-size -fsanitize=bool -fsanitize=enum -DMODULE \
    -DKBUILD_BASENAME='"$$TMP_BASE_SRC_NAME"' \
    -DKBUILD_MODNAME='"$$TMP_MODULE_NAME"'
```

#### struct_layout_ast
This is a Clang tool that used to dump structure layout information of source files.

How to use the tool to dump structure layout info of kernel file system sources:
```shell
TMP_KERNEL_INC=/usr/src/linux-headers-5.4.0-131-generic && \
TMP_CLANG_INC=/home/bing/usr/local/llvm-15.0.1/rel/lib/clang/15.0.1/include && \
TMP_SRC_FILE="*.c" && \
TMP_SRC_DIR=./ && \
TMP_ST_INFO_FILES="xx.struct.info" && \
TMP_SRC_FILES="nova.h inode.h" && \
TMP_BASE_SRC_NAME=na && \
TMP_MODULE_NAME=na && \
TMP_OUTPUT_NAME=xx.struct.layout && \
~/Silhouette/codebase/tools/struct_layout_ast/DumpStructLayout \
    --struct-layout-output-fname=$TMP_OUTPUT_NAME \
    --struct-info-fname-list=$TMP_ST_INFO_FILES \
    --src_files=$TMP_SRC_FILES \
    --src_dir=$TMP_SRC_DIR \
    $TMP_SRC_FILE \
    -- -x c \
    -nostdinc \
    -isystem $TMP_CLANG_INC \
    -I $TMP_KERNEL_INC/arch/x86/include \
    -I $TMP_KERNEL_INC/arch/x86/include/generated  \
    -I $TMP_KERNEL_INC/include \
    -I $TMP_KERNEL_INC/arch/x86/include/uapi \
    -I $TMP_KERNEL_INC/arch/x86/include/generated/uapi \
    -I $TMP_KERNEL_INC/include/uapi \
    -I $TMP_KERNEL_INC/include/generated/uapi \
    -include  $TMP_KERNEL_INC/include/linux/kconfig.h \
    -include  $TMP_KERNEL_INC/include/linux/compiler_types.h \
    -D__KERNEL__ \
    -Qunused-arguments -Wall -Wundef -Werror=strict-prototypes \
    -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar \
    -fno-PIE -Werror=implicit-function-declaration -Werror=implicit-int \
    -Wno-format-security -std=gnu89 -no-integrated-as -mno-sse -mno-mmx \
    -mno-sse2 -mno-3dnow -mno-avx -m64 -falign-loops=1 -mno-80387 \
    -mno-fp-ret-in-387 -mstack-alignment=8 -mskip-rax-setup \
    -mtune=generic -mno-red-zone -mcmodel=kernel -DCONFIG_X86_X32_ABI \
    -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 \
    -DCONFIG_AS_SSSE3=1 -DCONFIG_AS_AVX=1 -DCONFIG_AS_AVX2=1 \
    -DCONFIG_AS_AVX512=1 -DCONFIG_AS_SHA1_NI=1 -DCONFIG_AS_SHA256_NI=1 \
    -Wno-sign-compare -fno-asynchronous-unwind-tables \
    -mretpoline-external-thunk -fno-delete-null-pointer-checks \
    -Wno-frame-address -Wno-int-in-bool-context -Wno-address-of-packed-member \
    -O2 -Wframe-larger-than=1024 -fstack-protector-strong \
    -Wno-format-invalid-specifier -Wno-gnu -Wno-tautological-compare \
    -mno-global-merge -Wno-unused-const-variable -fno-omit-frame-pointer \
    -fno-optimize-sibling-calls -g -gdwarf-4 -pg -mfentry -DCC_USING_FENTRY \
    -Wdeclaration-after-statement -Wvla -Wno-pointer-sign -fno-strict-overflow \
    -fno-merge-all-constants -fno-stack-check -Werror=date-time \
    -Werror=incompatible-pointer-types \
    -fmacro-prefix-map=./= -Wno-initializer-overrides -Wno-unused-value \
    -Wno-format -Wno-sign-compare -Wno-format-zero-length \
    -Wno-uninitialized -fno-pic -fno-pie -fsanitize=kernel-address \
    -mllvm -asan-mapping-offset=0xdffffc0000000000  -mllvm -asan-globals=1 \
    -mllvm -asan-instrumentation-with-call-threshold=0  -mllvm -asan-stack=1 \
    --param asan-instrument-allocas=1 -fsanitize=shift \
    -fsanitize=integer-divide-by-zero  -fsanitize=unreachable \
    -fsanitize=vla-bound -fsanitize=signed-integer-overflow -fsanitize=bounds \
    -fsanitize=object-size -fsanitize=bool -fsanitize=enum -DMODULE \
    -DKBUILD_BASENAME='"$$TMP_BASE_SRC_NAME"' \
    -DKBUILD_MODNAME='"$$TMP_MODULE_NAME"'
```

#### struct_layout_pass
This is a LLVM pass that used to dump struct layout information of source files.

How to use it:
1. Build source code as the bytes code.
2. Use opt to run the pass.

How to use the tool to dump structure layout info of kernel file system sources:
```shell
# TODO
```

#### Useful Commands
How to dump AST of a kernel source file by Clang:
```shell
TMP_KERNEL_INC=/usr/src/linux-headers-5.4.0-131-generic && \
TMP_CLANG_INC=/home/bing/usr/local/llvm-15.0.1/rel/lib/clang/15.0.1/include && \
TMP_SRC_FILE=file.c && \
TMP_BASE_SRC_NAME=file && \
TMP_MODULE_NAME=nova && \
TMP_OUTPUT_NAME=xx.ast && \
clang \
    -Xclang -ast-dump -fsyntax-only -fno-color-diagnostics \
    -nostdinc \
    -isystem $TMP_CLANG_INC \
    -I $TMP_KERNEL_INC/arch/x86/include \
    -I $TMP_KERNEL_INC/arch/x86/include/generated  \
    -I $TMP_KERNEL_INC/include \
    -I $TMP_KERNEL_INC/arch/x86/include/uapi \
    -I $TMP_KERNEL_INC/arch/x86/include/generated/uapi \
    -I $TMP_KERNEL_INC/include/uapi \
    -I $TMP_KERNEL_INC/include/generated/uapi \
    -include  $TMP_KERNEL_INC/include/linux/kconfig.h \
    -include  $TMP_KERNEL_INC/include/linux/compiler_types.h \
    -D__KERNEL__ \
    -Qunused-arguments -Wall -Wundef -Werror=strict-prototypes \
    -Wno-trigraphs -fno-strict-aliasing -fno-common -fshort-wchar \
    -fno-PIE -Werror=implicit-function-declaration -Werror=implicit-int \
    -Wno-format-security -std=gnu89 -no-integrated-as -mno-sse -mno-mmx \
    -mno-sse2 -mno-3dnow -mno-avx -m64 -falign-loops=1 -mno-80387 \
    -mno-fp-ret-in-387 -mstack-alignment=8 -mskip-rax-setup \
    -mtune=generic -mno-red-zone -mcmodel=kernel -DCONFIG_X86_X32_ABI \
    -DCONFIG_AS_CFI=1 -DCONFIG_AS_CFI_SIGNAL_FRAME=1 -DCONFIG_AS_CFI_SECTIONS=1 \
    -DCONFIG_AS_SSSE3=1 -DCONFIG_AS_AVX=1 -DCONFIG_AS_AVX2=1 \
    -DCONFIG_AS_AVX512=1 -DCONFIG_AS_SHA1_NI=1 -DCONFIG_AS_SHA256_NI=1 \
    -Wno-sign-compare -fno-asynchronous-unwind-tables \
    -mretpoline-external-thunk -fno-delete-null-pointer-checks \
    -Wno-frame-address -Wno-int-in-bool-context -Wno-address-of-packed-member \
    -O2 -Wframe-larger-than=1024 -fstack-protector-strong \
    -Wno-format-invalid-specifier -Wno-gnu -Wno-tautological-compare \
    -mno-global-merge -Wno-unused-const-variable -fno-omit-frame-pointer \
    -fno-optimize-sibling-calls -g -gdwarf-4 -pg -mfentry -DCC_USING_FENTRY \
    -Wdeclaration-after-statement -Wvla -Wno-pointer-sign -fno-strict-overflow \
    -fno-merge-all-constants -fno-stack-check -Werror=date-time \
    -Werror=incompatible-pointer-types \
    -fmacro-prefix-map=./= -Wno-initializer-overrides -Wno-unused-value \
    -Wno-format -Wno-sign-compare -Wno-format-zero-length \
    -Wno-uninitialized -fno-pic -fno-pie -fsanitize=kernel-address \
    -mllvm -asan-mapping-offset=0xdffffc0000000000  -mllvm -asan-globals=1 \
    -mllvm -asan-instrumentation-with-call-threshold=0  -mllvm -asan-stack=1 \
    --param asan-instrument-allocas=1 -fsanitize=shift \
    -fsanitize=integer-divide-by-zero  -fsanitize=unreachable \
    -fsanitize=vla-bound -fsanitize=signed-integer-overflow -fsanitize=bounds \
    -fsanitize=object-size -fsanitize=bool -fsanitize=enum -DMODULE \
    -DKBUILD_BASENAME='"$$TMP_BASE_SRC_NAME"' \
    -DKBUILD_MODNAME='"$$TMP_MODULE_NAME"' \
    $TMP_SRC_FILE > $TMP_OUTPUT_NAME
```




