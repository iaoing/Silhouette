#include <sys/mount.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 2) {
		printf("USAGE: %s <mnt_point>\n", argv[0]);
		return -1;
	}

	ret = umount(argv[1]);

	if (ret != 0) {
		perror("XTEST: umount failed!\nERROR: ");
		return -1;
	}

	return 0;
}