#include <stdio.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

int main(int argc, char const *argv[])
{
    int fd = -1, ret = 0;
    off_t length = 0;
    struct stat stbuf;

    if (argc != 3) {
        printf("USAGE: %s <path> <length>\n", argv[0]);
        return -1;
    }

    // 0. create file.
    fd = creat(argv[1], 0644);

    if (fd < 0) {
        perror("XTEST: creat failed!\nERROR: ");
        return -1;
    }

    close(fd);

    // 1. truncate file.
    sscanf(argv[2], "%zu", &length);
    if (length > 104857600) {
        printf("XTEST: length: [%zu] is too big\n", length);
        return -1;
    }

    ret = truncate(argv[1], length + 8192);

    if (ret != 0) {
        perror("XTEST: truncate failed!\nERROR: ");
        return -1;
    }

    // 2. open file.
    fd = open(argv[1], O_RDWR);

    if (fd < 0) {
        perror("XTEST: open O_RDWR failed!\nERROR: ");
        return -1;
    }

    // 3. fstat file.
    ret = fstat(fd, &stbuf);

    if (ret != 0) {
        perror("XTEST: fstat failed!\nERROR: ");
        close(fd);
        return -1;
    }

    // 4. mmap file.
    char *ptr = mmap(NULL, stbuf.st_size, 
                PROT_READ | PROT_WRITE, 
                MAP_SHARED, fd, 0);

    if(ptr == MAP_FAILED){
        perror("XTEST: Mapping failed!\nERROR: ");
        close(fd);
        return -1;
    }

    // 5. write file.
    char *wrdata = (char*)malloc(length * sizeof(char));  // make it unaligned.
    for (int i = 0; i < length; ++i) {
        wrdata[i] = 'a';
    }
    memcpy(ptr + 4096, wrdata, length);
    msync(ptr + 4096, length, MS_SYNC);

    // 6. read file.
    memset(wrdata, 0, length);
    memcpy(wrdata, ptr + 4096, length);

    // 7. verify data.
    for (int i = 0; i < length; ++i) {
        if (wrdata[i] != 'a') {
            perror("XTEST: Mmap read the corrupted data!\nERROR: ");
            free(wrdata);
            close(fd);
            return -1;
        }
    }

    // 8. close file.
    free(wrdata);
    munmap(ptr, stbuf.st_size);
    close(fd);

    return 0;
}