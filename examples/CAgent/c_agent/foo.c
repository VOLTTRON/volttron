#include "foo.h"

int collatz(int n) {
  return (n % 2 == 0)
    ? (n / 2)
    : (3 * n + 1);
}
