
#if   defined(__LINUX__) || defined(__ANDROID__)
#	include <hal/linux/platform.h>
#else
#	error Unsupported platform
#endif
