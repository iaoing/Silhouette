#include <unistd.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;
	off_t length = 0;

	if (argc != 3) {
		printf("USAGE: %s <path> <length>\n", argv[0]);
		return -1;
	}

	sscanf(argv[2], "%zu", &length);
	if (length > 104857600) {
		printf("XTEST: length: [%zu] is too big\n", length);
		return -1;
	}

	ret = truncate(argv[1], length);

	if (ret != 0) {
		perror("XTEST: truncate failed!\nERROR: ");
		return -1;
	}

	return 0;
}