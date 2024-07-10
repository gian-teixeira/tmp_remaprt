AC_INIT([remaproute],[0.1],[cunha@dcc.ufmg.br])
AM_INIT_AUTOMAKE([foreign -Wall -Werror])

AC_USE_SYSTEM_EXTENSIONS

AC_PROG_CC
AC_REQUIRE(AC_PROG_CC)
AC_PROG_INSTALL
AC_PROG_LN_S

AC_CHECK_LIB([pthread], [pthread_create], [], [exit 1;])
AC_CHECK_LIB([pthread], [pthread_mutex_init], [], [exit 1;])
AC_CHECK_LIB([pcap], [pcap_loop], [], [exit 1;])
AC_CHECK_LIB([rt], [clock_gettime], [], [exit 1;])
AC_CHECK_LIB([net], [libnet_init], [], [exit 1;])
AC_CHECK_LIB([m], [exp], [], [exit 1;])

AC_CHECK_HEADERS([stdlib.h stddef.h stdio.h string.h unistd.h], [], [exit 1;])
AC_CHECK_HEADERS([math.h time.h pthread.h limits.h fcntl.h], [], [exit 1;])
AC_CHECK_HEADERS([assert.h inttypes.h], [], [exit 1;])
AC_CHECK_HEADERS([arpa/inet.h], [], [exit 1;])
AC_CHECK_HEADERS([sys/resource.h], [], [exit 1;])
AC_CHECK_HEADERS([libnet.h], [], [exit 1;])

AC_CHECK_FUNCS([strchr strdup strerror snprintf], [], [exit 1;])
AC_CHECK_FUNCS([clock_gettime gmtime_r], [], [exit 1;])
AC_CHECK_FUNCS([inet_pton inet_ntop], [], [exit 1;])
AC_CHECK_FUNCS([memset], [], [exit 1;])

AC_FUNC_MALLOC

AC_TYPE_UINT8_T
AC_TYPE_UINT16_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_SIZE_T
AC_TYPE_OFF_T

AC_CONFIG_HEADERS([config.h])
AC_CONFIG_FILES([Makefile src/Makefile])

AC_OUTPUT