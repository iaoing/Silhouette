# set from command line
LLVM15_HOME := $(LLVM15_HOME)
MODULE_NAME := $(MODULE_NAME)
FS_MODULE_SRC_DIR := $(FS_MODULE_SRC_DIR)
RUNTIME_TRACE_SRC := $(RUNTIME_TRACE_SRC)
INFO_DUMP_EXE := $(INFO_DUMP_EXE)
INFO_STRUCT_FNAME := $(INFO_STRUCT_FNAME)
INFO_POSIX_FN_FNAME := $(INFO_POSIX_FN_FNAME)
INFO_TRACE_FN_FNAME := $(INFO_TRACE_FN_FNAME)
STRUCT_LAYOUT_EXE := $(STRUCT_LAYOUT_EXE)
STRUCT_LAYOUT_FNAME := $(STRUCT_LAYOUT_FNAME)
INSTID_SRCLOC_MAP_FPATH := $(INSTID_SRCLOC_MAP_FPATH)

# function to check all variables are set
check_defined = \
    $(strip $(foreach 1,$1, \
        $(call __check_defined,$1,$(strip $(value 2)))))
__check_defined = \
    $(if $(value $1),, \
      $(error Undefined $1$(if $2, ($2))))

ifneq ($(MAKECMDGOALS),clean)
$(call check_defined, LLVM15_HOME)
$(call check_defined, MODULE_NAME)
$(call check_defined, FS_MODULE_SRC_DIR)
$(call check_defined, RUNTIME_TRACE_SRC)
$(call check_defined, INFO_DUMP_EXE)
$(call check_defined, INFO_STRUCT_FNAME)
$(call check_defined, INFO_POSIX_FN_FNAME)
$(call check_defined, INFO_TRACE_FN_FNAME)
$(call check_defined, STRUCT_LAYOUT_EXE)
$(call check_defined, STRUCT_LAYOUT_FNAME)
$(call check_defined, INSTID_SRCLOC_MAP_FPATH)
endif

# derived variables
LLVM15_LIB_INCLUDE := $(wildcard $(LLVM15_HOME)/lib/clang/15.*/include)
LLVM15_BIN=$(LLVM15_HOME)/bin

CLANG=$(LLVM15_BIN)/clang
CLANGXX=$(LLVM15_BIN)/clang++

CLANG_LINK=$(LLVM15_BIN)/llvm-link
CLANG_OPT=$(LLVM15_BIN)/opt
CLANG_LD=$(LLVM15_BIN)/ld.lld
CLANG_AR=$(LLVM15_BIN)/llvm-ar
CLANG_NM=$(LLVM15_BIN)/llvm-nm
CLANG_STRIP=$(LLVM15_BIN)/llvm-strip
CLANG_OBJCOPY=$(LLVM15_BIN)/llvm-objcopy
CLANG_OBJDUMP=$(LLVM15_BIN)/llvm-objdump
CLANG_READELF=$(LLVM15_BIN)/llvm-readelf
CLANG_HOSTCC=$(LLVM15_BIN)/clang
CLANG_HOSTCXX=$(LLVM15_BIN)/clang++
CLANG_HOSTAR=$(LLVM15_BIN)/llvm-ar
CLANG_HOSTLD=$(LLVM15_BIN)/ld.lld

CC=$(LLVM15_BIN)/clang
CXX=$(LLVM15_BIN)/clang++
CXXINC= -I../include -I$(LLVM15_HOME)/include -I$(LLVM15_HOME)/build/include
#CXXFLAGS= -g -c -O0 -ggdb -fPIC -std=c++17 $(CXXINC) -DDEBUG_GIRI_RUNTIME
CXXFLAGS= -g -O2 -c -fPIC -std=c++17 $(CXXINC)
#CXXLD= -L$(LLVM15_HOME)/lib -lLLVMSupport -ltinfo -lpthread -lstdc++fs
CXXLD= -L$(LLVM15_HOME)/lib -lLLVMSupport -lpthread -lstdc++fs

### kernel header
KERNEL_HEADER_DIR := /lib/modules/$(shell uname -r)/build

SI=../src/Si
GIRI=../src/Giri
UTILITY=../src/Utility
WITCHER=../src/Witcher
RUNTIME=../runtime
TOOLS=../tools

all: libnogiri.so

### libnogiru
libnogiri.so: TracingNoGiri.o BasicBlockNumbering.o LoadStoreNumbering.o TracingAnnot.o
	$(CXX) TracingNoGiri.o BasicBlockNumbering.o LoadStoreNumbering.o TracingAnnot.o -shared -o libnogiri.so

TracingNoGiri.o: $(GIRI)/TracingNoGiri.cpp
	$(CXX) $(CXXFLAGS) $(GIRI)/TracingNoGiri.cpp -o TracingNoGiri.o
BasicBlockNumbering.o: $(UTILITY)/BasicBlockNumbering.cpp
	$(CXX) $(CXXFLAGS) $(UTILITY)/BasicBlockNumbering.cpp -o BasicBlockNumbering.o
LoadStoreNumbering.o: $(UTILITY)/LoadStoreNumbering.cpp
	$(CXX) $(CXXFLAGS) $(UTILITY)/LoadStoreNumbering.cpp -o LoadStoreNumbering.o
TracingAnnot.o: $(SI)/TracingAnnot.cpp
	$(CXX) $(CXXFLAGS) $(SI)/TracingAnnot.cpp -o TracingAnnot.o

trace_bc: $(RUNTIME_TRACE_SRC)
	$(CLANG) \
		-Wp,-MD \
		-nostdinc -isystem $(LLVM15_LIB_INCLUDE) \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated  \
		-I$(KERNEL_HEADER_DIR)/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/uapi \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated/uapi \
		-I$(KERNEL_HEADER_DIR)/include/uapi \
		-I$(KERNEL_HEADER_DIR)/include/generated/uapi \
		-include $(KERNEL_HEADER_DIR)/include/linux/kconfig.h \
		-include $(KERNEL_HEADER_DIR)/include/linux/compiler_types.h \
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
		-DKBUILD_BASENAME='"trace"' \
		-DKBUILD_MODNAME='"'"$(MODULE_NAME)"'"' \
		-c $^ -emit-llvm \
		-o trace.bc ;

raw_bc:
	for filename in $(FS_MODULE_SRC_DIR)/*.c; \
		do \
			$(CLANG) \
				-Wp,-MD \
				-nostdinc -isystem $(LLVM15_LIB_INCLUDE) \
				-I$(KERNEL_HEADER_DIR)/arch/x86/include \
				-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated  \
				-I$(KERNEL_HEADER_DIR)/include \
				-I$(KERNEL_HEADER_DIR)/arch/x86/include/uapi \
				-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated/uapi \
				-I$(KERNEL_HEADER_DIR)/include/uapi \
				-I$(KERNEL_HEADER_DIR)/include/generated/uapi \
				-include $(KERNEL_HEADER_DIR)/include/linux/kconfig.h \
				-include $(KERNEL_HEADER_DIR)/include/linux/compiler_types.h \
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
				-DKBUILD_BASENAME='"$$(basename -s .c $$filename)"' \
				-DKBUILD_MODNAME='"'"$(MODULE_NAME)"'"' \
				-c $$filename -emit-llvm \
				-o ./$$(basename -s .c $$filename).bc ; \
		done
	$(CLANG_LINK) *.bc -o $(MODULE_NAME).bc

inst_bc: libnogiri.so raw_bc dump_info_1 dump_info_2 gen_struct_layout
	$(CLANG_OPT) \
		-enable-new-pm=0 \
		-load ./libnogiri.so \
		-mergereturn -bbnum -lsnum -trace-no-giri \
		-remove-bbnum -remove-lsnum \
		--annot-struct-fname-list=$(INFO_STRUCT_FNAME) \
		--annot-runtime-tracing-fname-list=$(INFO_TRACE_FN_FNAME) \
		--dump-id-src-fname=$(INSTID_SRCLOC_MAP_FPATH) \
		-stats -time-passes $(MODULE_NAME).bc \
		-o $(MODULE_NAME).ins.bc

raw_ko:
	cd $(FS_MODULE_SRC_DIR) && \
	make clean && \
	make CC=$(CLANG) LD=$(CLANG_LD) AR=$(CLANG_AR) NM=$(CLANG_NM) STRIP=$(CLANG_STRIP) \
	     OBJCOPY=$(CLANG_OBJCOPY) OBJDUMP=$(CLANG_OBJDUMP) READELF=$(CLANG_READELF) \
		 HOSTCC=$(CLANG_HOSTCC) HOSTCXX=$(CLANG_HOSTCXX) HOSTAR=$(CLANG_HOSTAR) \
		 HOSTLD=$(CLANG_HOSTLD) V=1

inst_ko: inst_bc trace_bc
	$(CLANG_LINK) $(MODULE_NAME).ins.bc trace.bc -o $(MODULE_NAME).ins.all.bc
	$(CLANG) -mcmodel=kernel -c $(MODULE_NAME).ins.all.bc -o $(MODULE_NAME).ins.all.o
	cd $(FS_MODULE_SRC_DIR) && \
	make clean && \
	make CC=$(CLANG) LD=$(CLANG_LD) AR=$(CLANG_AR) NM=$(CLANG_NM) STRIP=$(CLANG_STRIP) \
	     OBJCOPY=$(CLANG_OBJCOPY) OBJDUMP=$(CLANG_OBJDUMP) READELF=$(CLANG_READELF) \
		 HOSTCC=$(CLANG_HOSTCC) HOSTCXX=$(CLANG_HOSTCXX) HOSTAR=$(CLANG_HOSTAR) \
		 HOSTLD=$(CLANG_HOSTLD) V=1 && \
	rm $(MODULE_NAME).mod.* && \
	rm $(MODULE_NAME).ko && \
	cd -
	cp $(MODULE_NAME).ins.all.o $(FS_MODULE_SRC_DIR)/$(MODULE_NAME).o
	cd $(FS_MODULE_SRC_DIR) && \
	make CC=$(CLANG) LD=$(CLANG_LD) AR=$(CLANG_AR) NM=$(CLANG_NM) STRIP=$(CLANG_STRIP) \
	     OBJCOPY=$(CLANG_OBJCOPY) OBJDUMP=$(CLANG_OBJDUMP) READELF=$(CLANG_READELF) \
		 HOSTCC=$(CLANG_HOSTCC) HOSTCXX=$(CLANG_HOSTCXX) HOSTAR=$(CLANG_HOSTAR) \
		 HOSTLD=$(CLANG_HOSTLD) V=1

dump_info_1:
	LD_LIBRARY_PATH=$(LLVM15_HOME)/lib:$(LD_LIBRARY_PATH) \
	$(INFO_DUMP_EXE) \
		--output_struct_fname="/dev/null" \
		--output_vfs_func_fname="/dev/null" \
		--output_all_func_fname=$(INFO_TRACE_FN_FNAME) \
		--src_files="$(RUNTIME_TRACE_SRC)" \
		$(RUNTIME_TRACE_SRC) \
		-- \
		-x c \
		-nostdinc -isystem $(LLVM15_LIB_INCLUDE) \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated  \
		-I$(KERNEL_HEADER_DIR)/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/uapi \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated/uapi \
		-I$(KERNEL_HEADER_DIR)/include/uapi \
		-I$(KERNEL_HEADER_DIR)/include/generated/uapi \
		-include $(KERNEL_HEADER_DIR)/include/linux/kconfig.h \
		-include $(KERNEL_HEADER_DIR)/include/linux/compiler_types.h \
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
		-fsanitize=object-size -fsanitize=bool -fsanitize=enum

dump_info_2:
	cd $(FS_MODULE_SRC_DIR) && \
	LD_LIBRARY_PATH=$(LLVM15_HOME)/lib:$(LD_LIBRARY_PATH) \
	$(INFO_DUMP_EXE) \
		--output_struct_fname=$(INFO_STRUCT_FNAME) \
		--output_vfs_func_fname=$(INFO_POSIX_FN_FNAME) \
		--output_all_func_fname="dev/null" \
		--src_dir="$(FS_MODULE_SRC_DIR)" \
		$(FS_MODULE_SRC_DIR)/*.c \
		-- \
		-x c \
		-nostdinc -isystem $(LLVM15_LIB_INCLUDE) \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated  \
		-I$(KERNEL_HEADER_DIR)/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/uapi \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated/uapi \
		-I$(KERNEL_HEADER_DIR)/include/uapi \
		-I$(KERNEL_HEADER_DIR)/include/generated/uapi \
		-include $(KERNEL_HEADER_DIR)/include/linux/kconfig.h \
		-include $(KERNEL_HEADER_DIR)/include/linux/compiler_types.h \
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
		-DKBUILD_BASENAME='"whatevenname"' \
		-DKBUILD_MODNAME='"whatevenname"'

gen_struct_layout: dump_info_2
	cd $(FS_MODULE_SRC_DIR) && \
	LD_LIBRARY_PATH=$(LLVM15_HOME)/lib:$(LD_LIBRARY_PATH) \
	$(STRUCT_LAYOUT_EXE) \
		--struct-layout-output-fname=$(STRUCT_LAYOUT_FNAME) \
		--struct-info-fname-list=$(INFO_STRUCT_FNAME) \
		--src_dir="$(FS_MODULE_SRC_DIR)" \
		$(FS_MODULE_SRC_DIR)/*.c \
		-- \
		-x c \
		-nostdinc -isystem $(LLVM15_LIB_INCLUDE) \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated  \
		-I$(KERNEL_HEADER_DIR)/include \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/uapi \
		-I$(KERNEL_HEADER_DIR)/arch/x86/include/generated/uapi \
		-I$(KERNEL_HEADER_DIR)/include/uapi \
		-I$(KERNEL_HEADER_DIR)/include/generated/uapi \
		-include $(KERNEL_HEADER_DIR)/include/linux/kconfig.h \
		-include $(KERNEL_HEADER_DIR)/include/linux/compiler_types.h \
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
		-DKBUILD_BASENAME='"whatevenname"' \
		-DKBUILD_MODNAME='"whatevenname"'

### misc
clean:
	rm -f *.o *.so *.a *.d *.bc *.ll *.annot $(all)
