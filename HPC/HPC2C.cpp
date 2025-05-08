#include <iostream>
#include <vector>
#include <chrono>
#include <omp.h>
#include <algorithm>

using namespace std;
using namespace chrono;

// ------------------------------
// Sequential Bubble Sort
// ------------------------------
void sequentialBubbleSort(vector<int>& arr) {
    int n = arr.size(); // Get the size of the array
    // Outer loop to go through the entire array
    for (int i = 0; i < n - 1; ++i) 
        // Inner loop to compare adjacent elements
        for (int j = 0; j < n - i - 1; ++j) 
            // Swap if elements are in wrong order
            if (arr[j] > arr[j + 1]) 
                swap(arr[j], arr[j + 1]);
}

// ------------------------------
// Parallel Bubble Sort using OpenMP
// ------------------------------
void parallelBubbleSort(vector<int>& arr) {
    int n = arr.size(); // Get the size of the array
    for (int i = 0; i < n; ++i) {
        // Parallelize the inner loop for each iteration of the outer loop
        #pragma omp parallel for
        for (int j = i % 2; j < n - 1; j += 2) {
            // Swap if elements are in wrong order
            if (arr[j] > arr[j + 1]) {
                swap(arr[j], arr[j + 1]);
            }
        }
    }
}

// ------------------------------
// Merge Function
// ------------------------------
void merge(vector<int>& arr, int l, int m, int r) {
    // Create temporary arrays for the left and right halves
    vector<int> left(arr.begin() + l, arr.begin() + m + 1);
    vector<int> right(arr.begin() + m + 1, arr.begin() + r + 1);

    int i = 0, j = 0, k = l;

    // Merge the left and right halves into the original array
    while (i < left.size() && j < right.size()) {
        if (left[i] <= right[j])
            arr[k++] = left[i++];
        else
            arr[k++] = right[j++];
    }

    // Copy remaining elements of left array
    while (i < left.size())
        arr[k++] = left[i++];
    // Copy remaining elements of right array
    while (j < right.size())
        arr[k++] = right[j++];
}

// ------------------------------
// Sequential Merge Sort
// ------------------------------
void sequentialMergeSort(vector<int>& arr, int l, int r) {
    if (l < r) {
        int m = l + (r - l) / 2; // Find the middle point
        sequentialMergeSort(arr, l, m); // Recursively sort the left half
        sequentialMergeSort(arr, m + 1, r); // Recursively sort the right half
        merge(arr, l, m, r); // Merge the two halves
    }
}

// ------------------------------
// Parallel Merge Sort using OpenMP
// ------------------------------
void parallelMergeSort(vector<int>& arr, int l, int r, int depth = 0) {
    if (l < r) {
        int m = l + (r - l) / 2; // Find the middle point

        // Parallelize the sorting if depth is less than 4
        if (depth < 4) {
            #pragma omp parallel sections
            {
                #pragma omp section
                parallelMergeSort(arr, l, m, depth + 1);
                #pragma omp section
                parallelMergeSort(arr, m + 1, r, depth + 1);
            }
        } else {
            sequentialMergeSort(arr, l, m); // Fall back to sequential if depth >= 4
            sequentialMergeSort(arr, m + 1, r); // Fall back to sequential if depth >= 4
        }

        merge(arr, l, m, r); // Merge the two halves
    }
}

// ------------------------------
// Timing Helper
// ------------------------------
void measureSortPerformance() {
    const int SIZE = 5000;
    vector<int> original(SIZE);

    // Generate random data
    srand(time(0));
    for (int i = 0; i < SIZE; ++i)
        original[i] = rand() % 10000;

    // Sequential Bubble Sort
    vector<int> bubbleSeq = original;
    auto start = high_resolution_clock::now(); // Record start time
    sequentialBubbleSort(bubbleSeq); // Call sequential bubble sort
    auto end = high_resolution_clock::now(); // Record end time
    cout << "Sequential Bubble Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    // Parallel Bubble Sort
    vector<int> bubblePar = original;
    start = high_resolution_clock::now();
    parallelBubbleSort(bubblePar); // Call parallel bubble sort
    end = high_resolution_clock::now();
    cout << "Parallel Bubble Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    // Sequential Merge Sort
    vector<int> mergeSeq = original;
    start = high_resolution_clock::now();
    sequentialMergeSort(mergeSeq, 0, mergeSeq.size() - 1); // Call sequential merge sort
    end = high_resolution_clock::now();
    cout << "Sequential Merge Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    // Parallel Merge Sort
    vector<int> mergePar = original;
    start = high_resolution_clock::now();
    parallelMergeSort(mergePar, 0, mergePar.size() - 1); // Call parallel merge sort
    end = high_resolution_clock::now();
    cout << "Parallel Merge Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";
}

// ------------------------------
// Main
// ------------------------------
int main() {
    measureSortPerformance(); // Measure the performance of the sorting algorithms
    return 0;
}
