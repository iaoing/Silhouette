#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;
	struct stat buf;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		return -1;
	}

	ret = stat(argv[1], &buf);

	if (ret != 0) {
		perror("XTEST: stat failed!\nERROR: ");
		return -1;
	}

	return 0;
}