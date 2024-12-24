#include <fcntl.h>
#include <errno.h>
#include <dirent.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char const *argv[])
{
	int ret = 0;
	struct dirent *d = NULL;
	int fd = -1;
	char buf[4096];
	off_t basep;

	if (argc != 2) {
		printf("USAGE: %s <dir_path>\n", argv[0]);
		return -1;
	}

	fd = open(argv[1], O_RDONLY);

	if (fd < 0) {
		perror("XTEST: open failed!\nERROR: ");
		return -1;
	}

	ret = getdirentries(fd, buf, sizeof(buf), &basep);
	if (ret == -1) {
		perror("XTEST: getdirentries failed!\nERROR: ");
		close(fd);
		return -1;
	}

	d=(struct dirent *)buf;
	printf("dentry name: [%s]\n",d->d_name);
	close(fd);

	return 0;
}