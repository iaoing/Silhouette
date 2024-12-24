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

	fd = open(argv[1], O_RDWR);

	if (fd < 0) {
		perror("XTEST: open O_RDWR failed!\nERROR: ");
		return -1;
	}

	close(fd);

	return 0;
}