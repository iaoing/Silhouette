#include <unistd.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 3) {
		printf("USAGE: %s <target> <linkpath>\n", argv[0]);
		return -1;
	}

	ret = symlink(argv[1], argv[2]);

	if (ret != 0) {
		perror("XTEST: symlink failed!\nERROR: ");
		return -1;
	}

	return 0;
}