#include "DiskContent.h"

#include <string>

void usage(const char *exename) {
    printf("usage:\n");
    printf("%s <path> <output_file> <description>\n", exename);
    printf("path: the directory path\n");
    printf("output_file: the output file name\n");
    printf("description: the description of this mounted image\n");
}

int main(int argc, char const *argv[])
{
    if (argc != 4) {
        usage(argv[0]);
        return 0;
    }

    std::string dirpath(argv[1]);
    std::string ofile(argv[2]);
    std::string desc(argv[3]);

    DiskContents ctx;
    ctx.reset(dirpath, desc);
    ctx.get_contents(dirpath);

    if (ctx.size() == 0) {
        printf("no files inside %s, or error occured.\n", argv[1]);
        return 0;
    }

    size_t wr_bytes = 0;
    wr_bytes = ctx.output_contents(ofile);
    printf("%zu bytes are written to %s for disk %s (%s)\n", wr_bytes, argv[2], argv[1], argv[3]);

    return 0;
}
