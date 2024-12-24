#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		return -1;
	}

	ret = mkdir(argv[1], 0777);

	if (ret != 0) {
		perror("XTEST: mkdir 0777 failed!\nERROR: ");
		return -1;
	}

	return 0;
}