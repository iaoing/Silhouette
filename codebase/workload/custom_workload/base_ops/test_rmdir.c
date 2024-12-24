#include <unistd.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		return -1;
	}

	ret = rmdir(argv[1]);

	if (ret != 0) {
		perror("XTEST: rmdir failed!\nERROR: ");
		return -1;
	}

	return 0;
}