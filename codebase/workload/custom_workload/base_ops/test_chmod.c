#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		printf("Change <path> to be executable by the owner\n");
		return -1;
	}

	// ret = chmod(argv[1], S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
	ret = chmod(argv[1], 0777);

	if (ret != 0) {
		perror("XTEST: chmod failed!\nERROR: ");
		return -1;
	}

	return 0;
}