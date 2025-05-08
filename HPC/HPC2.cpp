#include <iostream>
#include <vector>
#include <chrono>
#include <omp.h>
#include <algorithm>

using namespace std;
using namespace chrono;

void sequentialBubbleSort(vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n - 1; ++i)
        for (int j = 0; j < n - i - 1; ++j)
            if (arr[j] > arr[j + 1])
                swap(arr[j], arr[j + 1]);
}

void parallelBubbleSort(vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n; ++i) {
        #pragma omp parallel for
        for (int j = i % 2; j < n - 1; j += 2) {
            if (arr[j] > arr[j + 1]) {
                swap(arr[j], arr[j + 1]);
            }
        }
    }
}

void merge(vector<int>& arr, int l, int m, int r) {
    vector<int> left(arr.begin() + l, arr.begin() + m + 1);
    vector<int> right(arr.begin() + m + 1, arr.begin() + r + 1);

    int i = 0, j = 0, k = l;

    while (i < left.size() && j < right.size()) {
        if (left[i] <= right[j])
            arr[k++] = left[i++];
        else
            arr[k++] = right[j++];
    }

    while (i < left.size())
        arr[k++] = left[i++];
    while (j < right.size())
        arr[k++] = right[j++];
}

void sequentialMergeSort(vector<int>& arr, int l, int r) {
    if (l < r) {
        int m = l + (r - l) / 2;
        sequentialMergeSort(arr, l, m);
        sequentialMergeSort(arr, m + 1, r);
        merge(arr, l, m, r);
    }
}

void parallelMergeSort(vector<int>& arr, int l, int r, int depth = 0) {
    if (l < r) {
        int m = l + (r - l) / 2;

        if (depth < 4) {
            #pragma omp parallel sections
            {
                #pragma omp section
                parallelMergeSort(arr, l, m, depth + 1);
                #pragma omp section
                parallelMergeSort(arr, m + 1, r, depth + 1);
            }
        } else {
            sequentialMergeSort(arr, l, m);
            sequentialMergeSort(arr, m + 1, r);
        }

        merge(arr, l, m, r);
    }
}

void measureSortPerformance() {
    const int SIZE = 5000;
    vector<int> original(SIZE);

    srand(time(0));
    for (int i = 0; i < SIZE; ++i)
        original[i] = rand() % 10000;

    vector<int> bubbleSeq = original;
    auto start = high_resolution_clock::now();
    sequentialBubbleSort(bubbleSeq);
    auto end = high_resolution_clock::now();
    cout << "Sequential Bubble Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    vector<int> bubblePar = original;
    start = high_resolution_clock::now();
    parallelBubbleSort(bubblePar);
    end = high_resolution_clock::now();
    cout << "Parallel Bubble Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    vector<int> mergeSeq = original;
    start = high_resolution_clock::now();
    sequentialMergeSort(mergeSeq, 0, mergeSeq.size() - 1);
    end = high_resolution_clock::now();
    cout << "Sequential Merge Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";

    vector<int> mergePar = original;
    start = high_resolution_clock::now();
    parallelMergeSort(mergePar, 0, mergePar.size() - 1);
    end = high_resolution_clock::now();
    cout << "Parallel Merge Sort Time: " 
         << duration_cast<milliseconds>(end - start).count() << " ms\n";
}

int main() {
    measureSortPerformance();
    return 0;
}
