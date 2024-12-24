#include <sys/time.h>
#include <errno.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int ret = 0;
	struct timeval times[2];
	struct timezone tz;

	if (argc != 2) {
		printf("USAGE: %s <path>\n", argv[0]);
		return -1;
	}

	if (gettimeofday(&times[1], &tz) == -1) {
		perror("XTEST: gettimeofday failed!\nERROR: ");
		return -1;
	}

	if (gettimeofday(&times[0], &tz) == -1) {
		perror("XTEST: gettimeofday failed!\nERROR: ");
		return -1;
	}

	ret = utimes(argv[1], times);

	if (ret != 0) {
		perror("XTEST: utimes failed!\nERROR: ");
		return -1;
	} 

	return 0;
}