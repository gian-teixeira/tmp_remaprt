#ifndef __LOG_HEADER__
#define __LOG_HEADER__

#include <inttypes.h>

#define LOG_FATAL 1
#define LOG_DEBUG 5
#define LOG_WARN 50
#define LOG_INFO 100
#define LOG_EXTRA 1000

/* initializes the global logger. verbosity specifies what gets printed. path
 * is where the log will be saved. nbackups say how many backups you want to
 * keep. filesize specifies the maximum log file size before creating a new
 * one. returns 0 on success, 1 otherwise. */
void log_init(unsigned verbosity, const char *path, unsigned nbackups,
		unsigned filesize);

void log_destroy(void);

/* writes all log messages to disk. */
void log_flush(void);

/* fmt and ... work like in printf. this function only prints the message if
 * verbosity is less that the value passed to log_init. */
void logd(unsigned verbosity, const char *fmt, ...);

/* if ernno is set, prints the file name, the line number, and the standard
 * error message. does nothing if errno is not set. */
void loge(unsigned verbosity, const char *file, int lineno);

/* if ernno is set, prints the file name and line number, the error message,
 * then exits the program. does nothing if errno is not set. */
void logea(const char *file, int lineno, const char *msg);

/* logs the IP address in dotted-decimal format. */
void logip(unsigned verbosity, uint32_t ip);

/* returns 1 if verbosity would result in messages being printed. */
int log_true(unsigned verbosity);

#endif
