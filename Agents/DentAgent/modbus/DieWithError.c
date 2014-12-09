#include <stdio.h>  /* for perror() */
#include <stdarg.h>
#include <string.h>

#include <Python.h>

/* SDH : set up a python exception instead of just calling exit() */
void DieWithError(const char *fmt, ...)
{
  char error_msg[1024];
  int n = 0;
  va_list ap;
  va_start(ap, fmt);

  n += vsnprintf(error_msg, 1023, fmt, ap);
  n += snprintf(error_msg + n, 1023 - n, ": %s", strerror(errno));
  error_msg[n] = '\0';

  PyErr_SetString(PyExc_IOError, error_msg);
  va_end(ap);
}
