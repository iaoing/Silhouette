#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char const *argv[])
{
	int fd = -1;
	int ret = 0;
	char *buf;
	ssize_t rd_bytes = 0;
	ssize_t size = 0;

	if (argc != 3) {
		printf("USAGE: %s <path> <size>\n", argv[0]);
		printf("Read <size> bytes from the beginning of <path>.\n");
		return -1;
	}

	fd = open(argv[1], O_RDWR);
	if (fd < 0) {
		perror("XTEST: open O_RDWR failed!\nERROR: ");
		return -1;
	}

	sscanf(argv[2], "%zu", &size);
	buf = (char*)malloc(size);
	if (buf == NULL) {
		perror("XTEST: malloc failed!\nERROR: ");
		goto out_file;
	}
	if (size > 10485760) {
		printf("XTEST: size: [%zu] is too big\n", size);
		goto out_file;
	}

	rd_bytes = read(fd, buf, size);
	if (rd_bytes != size) {
		printf("XTEST: read failed! size: [%zu]. \n", rd_bytes);
		perror("ERROR: ");
	} else {
		printf("read size: [%zu], buf: [%s]\n", rd_bytes, buf);
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