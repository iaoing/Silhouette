#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char const *argv[])
{
	int rd_bytes = 0;
	size_t size = 0;
	char *buf = NULL;

	if (argc != 3) {
		printf("USAGE: %s <path> <size>\n", argv[0]);
		return -1;
	}

	sscanf(argv[2], "%zu", &size);
	buf = (char*)malloc(size);
	if (buf == NULL) {
		return -1;
	}
	if (size > 10485760) {
		printf("XTEST: size: [%zu] is too big\n", size);
	}

	rd_bytes = (int)readlink(argv[1], buf, size);

	if (rd_bytes == -1) {
		printf("XTEST: readlink failed! size: [%d]. \n", rd_bytes);
		perror("ERROR: ");
		free(buf);
		return -1;
	} else {
		printf("readlink size: [%d], buf: [%s]\n", rd_bytes, buf);
		free(buf);
	}

	return 0;
}