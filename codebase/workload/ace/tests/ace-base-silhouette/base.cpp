#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <string>
#include <iostream>
#include <dirent.h>
#include <cstring>
#include <cstdlib>
#include <errno.h>
#include <sys/xattr.h>

#include "../BaseTestCase.h"

using std::string;

#define TEST_FILE_PERMS  ((mode_t) (S_IRWXU | S_IRWXG | S_IRWXO))

namespace fs_testing {
    namespace tests {

        class testName: public BaseTestCase {
        public:
            virtual int setup() override {

                return 0;
            }

            virtual int run() override {

                return 0;
            }

        private:

        };

    }  // namespace tests
}  // namespace fs_testing

int main(int argc, char const *argv[]) {

    if (argc == 3) {
        string dir_name = string(argv[1]);
        long fs_size = std::strtol(argv[2], NULL, 10);

        fs_testing::tests::testName test_obj;
        fs_testing::tests::BaseTestCase *tester = &test_obj;

        tester->init_values(dir_name, fs_size);
        return tester->Run(dir_name);
    } else if (argc == 4) {
        string dir_name = string(argv[1]);
        long fs_size = std::strtol(argv[2], NULL, 10);
        string ctx_store_dir = string(argv[3]);

        fs_testing::tests::testName test_obj;
        fs_testing::tests::BaseTestCase *tester = &test_obj;

        tester->init_values(dir_name, fs_size, ctx_store_dir);
        return tester->Run(dir_name);
    } else {
        return -1;
    }

    return 0;
}