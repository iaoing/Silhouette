#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char const *argv[])
{
	int fd = -1;
	int ret = 0;
	char *buf;
	ssize_t wr_bytes = 0;
	ssize_t size = 0;
	off_t offset = 0;

	if (argc != 4) {
		printf("USAGE: %s <path> <size> <offset>\n", argv[0]);
		return -1;
	}

	fd = open(argv[1], O_RDWR);
	if (fd < 0) {
		perror("XTEST: open O_RDWR failed!\nERROR: ");
		return -1;
	}

	sscanf(argv[2], "%zu", &size);
	sscanf(argv[3], "%zu", &offset);
	buf = (char*)malloc(size);
	if (buf == NULL) {
		perror("XTEST: malloc failed!\nERROR: ");
		goto out_file;
	}
	if (size > 10485760) {
		printf("XTEST: size: [%zu] is too big\n", size);
		goto out_file;
	}
	if (offset > 104857600) {
		printf("XTEST: offset: [%zu] is too big\n", offset);
		goto out_file;
	}
	memset(buf, '1', size);

	wr_bytes = pwrite(fd, buf, size, offset);
	if (wr_bytes != size) {
		printf("XTEST: pwrite failed! size: [%zu]. \n", wr_bytes);
		perror("ERROR: ");
	}

out_file:
	if (buf) free(buf);
	ret = close(fd);
	if (ret != 0) {
		perror("XTEST: close failed!\nERROR: ");
		return -1;
	}


	return 0;
}