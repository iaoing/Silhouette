#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char const *argv[])
{
	int fd = -1;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		return -1;
	}

	fd = creat(argv[1], 0644);

	if (fd < 0) {
		perror("XTEST: creat failed!\nERROR: ");
		return -1;
	}

	close(fd);

	return 0;
}