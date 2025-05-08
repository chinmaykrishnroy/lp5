#include <iostream>
#include <vector>
#include <omp.h>

using namespace std;

// ----------------------------
// Parallel Breadth-First Search (BFS) using OpenMP
// ----------------------------
void parallelBFS(const vector<vector<int>>& graph, int start) {
    int n = graph.size();
    vector<int> visited(n, 0);       // Keeps track of visited nodes
    vector<int> frontier;            // Current BFS frontier (nodes to explore)

    visited[start] = 1;
    frontier.push_back(start);

    cout << "Parallel BFS: ";

    while (!frontier.empty()) {
        vector<int> next_frontier;   // Stores nodes for the next level of BFS

        // Parallel region for processing the current frontier
        #pragma omp parallel
        {
            vector<int> local_next;  // Thread-local storage for discovered nodes

            // Distribute frontier processing among threads
            #pragma omp for nowait
            for (int i = 0; i < frontier.size(); ++i) {
                int u = frontier[i];

                // Print node (use critical section to avoid garbled output)
                #pragma omp critical
                cout << u << " ";

                // Explore neighbors
                for (int v : graph[u]) {
                    // Check and mark visited inside a critical section
                    #pragma omp critical
                    {
                        if (visited[v] == 0) {
                            visited[v] = 1;
                            local_next.push_back(v);
                        }
                    }
                }
            }

            // Merge thread-local results into global next_frontier
            #pragma omp critical
            next_frontier.insert(next_frontier.end(), local_next.begin(), local_next.end());
        }

        frontier = next_frontier;  // Move to next level
    }

    cout << endl;
}

// ----------------------------
// Parallel Depth-First Search (DFS) using OpenMP tasks
// ----------------------------
void parallelDFSUtil(const vector<vector<int>>& graph, int node, vector<int>& visited) {
    bool alreadyVisited;

    // Atomically check and mark node as visited
    #pragma omp critical
    {
        alreadyVisited = visited[node];
        if (!alreadyVisited) {
            visited[node] = 1;
            cout << node << " ";
        }
    }

    if (alreadyVisited) return;

    // Parallelize over neighbors using tasks
    #pragma omp parallel for
    for (int i = 0; i < graph[node].size(); ++i) {
        int v = graph[node][i];

        if (!visited[v]) {
            #pragma omp task
            parallelDFSUtil(graph, v, visited);
        }
    }

    #pragma omp taskwait  // Wait for all tasks to complete
}

// Wrapper to launch DFS in parallel region
void parallelDFS(const vector<vector<int>>& graph, int start) {
    int n = graph.size();
    vector<int> visited(n, 0);

    cout << "Parallel DFS: ";

    #pragma omp parallel
    {
        #pragma omp single
        parallelDFSUtil(graph, start, visited);
    }

    cout << endl;
}

// ----------------------------
// Main Function
// ----------------------------
int main() {
    // Define graph as adjacency list
    vector<vector<int>> graph = {
        {1, 2},    // 0
        {0, 3, 4}, // 1
        {0, 4},    // 2
        {1, 5},    // 3
        {1, 2, 5}, // 4
        {3, 4}     // 5
    };

    int startNode = 0;

    parallelBFS(graph, startNode);
    parallelDFS(graph, startNode);

    return 0;
}
