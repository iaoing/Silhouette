#include <sys/mount.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;

	if (argc != 4 && argc != 5) {
		printf("USAGE: %s <device> <mnt_point> <fs_type> [data]\n", argv[0]);
		printf("mount with 0 flag.\n");
		return -1;
	}

	if (argc == 4) {
		printf("mount %s %s %s 0 NULL\n", argv[1], argv[2], argv[3]);
		ret = mount(argv[1], argv[2], argv[3], 0, NULL);
	} else {
		printf("mount %s %s %s 0 %s\n", argv[1], argv[2], argv[3], argv[4]);
		ret = mount(argv[1], argv[2], argv[3], 0, argv[4]);
	}

	if (ret != 0) {
		perror("XTEST: mount failed!\nERROR: ");
		return -1;
	}

	return 0;
}