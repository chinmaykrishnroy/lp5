#include <iostream>
#include <vector>
#include <cstdlib>
#include <ctime>
#include <omp.h>

using namespace std;

int main() {
    const int SIZE = 1000000; // Define the size of the vector
    vector<int> data(SIZE);  // Create a vector to store the data

    // Fill vector with random integers
    srand(time(0)); // Seed for random number generation
    for (int i = 0; i < SIZE; ++i) {
        data[i] = rand() % 10000; // Fill the vector with random numbers between 0 and 9999
    }

    int minVal = data[0]; // Initialize min value to the first element
    int maxVal = data[0]; // Initialize max value to the first element
    long long sum = 0;    // Initialize sum to 0

    // Parallel Reduction
    #pragma omp parallel for reduction(min:minVal) reduction(max:maxVal) reduction(+:sum)
    for (int i = 0; i < SIZE; ++i) {
        if (data[i] < minVal) minVal = data[i]; // Find minimum value
        if (data[i] > maxVal) maxVal = data[i]; // Find maximum value
        sum += data[i]; // Add value to sum
    }

    double average = static_cast<double>(sum) / SIZE; // Calculate average

    // Print results
    cout << "Parallel Reduction Results:\n";
    cout << "Min: " << minVal << "\n";   // Print the minimum value
    cout << "Max: " << maxVal << "\n";   // Print the maximum value
    cout << "Sum: " << sum << "\n";      // Print the sum of the values
    cout << "Average: " << average << "\n"; // Print the average

    return 0;
}
