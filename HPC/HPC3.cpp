#include <iostream>
#include <vector>
#include <cstdlib>
#include <ctime>
#include <omp.h>

using namespace std;

int main() {
    const int SIZE = 1000000;
    vector<int> data(SIZE);

    srand(time(0));
    for (int i = 0; i < SIZE; ++i) {
        data[i] = rand() % 10000;
    }

    int minVal = data[0];
    int maxVal = data[0];
    long long sum = 0;

    #pragma omp parallel for reduction(min:minVal) reduction(max:maxVal) reduction(+:sum)
    for (int i = 0; i < SIZE; ++i) {
        if (data[i] < minVal) minVal = data[i];
        if (data[i] > maxVal) maxVal = data[i];
        sum += data[i];
    }

    double average = static_cast<double>(sum) / SIZE;

    cout << "Parallel Reduction Results:\n";
    cout << "Min: " << minVal << "\n";
    cout << "Max: " << maxVal << "\n";
    cout << "Sum: " << sum << "\n";
    cout << "Average: " << average << "\n";

    return 0;
}
