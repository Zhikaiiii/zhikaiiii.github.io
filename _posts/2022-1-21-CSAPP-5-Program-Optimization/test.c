#include "stdio.h"

void main(){
    int A[9] = {0, 1, 2, 4, 8, 16, 32, 64, 128};

    int *B = A + 3;
    printf("%d", B[1]);
}