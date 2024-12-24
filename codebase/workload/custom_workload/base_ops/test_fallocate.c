#define _GNU_SOURCE
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int fd;
	int ret = 0;
	off_t offset = 0;
	off_t length = 0;
	int keep_size = 0;

	if (argc != 5) {
		printf("USAGE: %s <str:path> <int:offset> <int:length> <int:keep_size>\n", argv[0]);
		return -1;
	}

	sscanf(argv[2], "%zu", &offset);
	sscanf(argv[3], "%zu", &length);
	sscanf(argv[4], "%d", &keep_size);
	if (offset > 104857600) {
		printf("XTEST: offset: [%zu] is too large\n", offset);
		return -1;
	}
	if (length > 104857600) {
		printf("XTEST: length: [%zu] is too large\n", length);
		return -2;
	}

	fd = open(argv[1], O_RDWR);
	if (fd < 0) {
		perror("XTEST: open O_RDWR failed!\nERROR: ");
		return -3;
	}

	if (keep_size) {
		ret = fallocate(fd, 0, offset, length);
	} else {
		ret = fallocate(fd, FALLOC_FL_KEEP_SIZE, offset, length);
	}

	if (ret != 0) {
		perror("XTEST: fallocate failed!\nERROR: ");
		return -4;
	}

	return 0;
}