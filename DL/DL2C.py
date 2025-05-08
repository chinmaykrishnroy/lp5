# Import necessary libraries
import numpy as np  # Numerical operations
import pandas as pd  # DataFrame and data handling
import matplotlib.pyplot as plt  # Plotting
import seaborn as sns  # Statistical data visualization
from keras.datasets import imdb  # IMDB sentiment dataset
from keras import models, layers  # Keras model and layer APIs
from sklearn.model_selection import train_test_split  # Splitting data
from sklearn.metrics import accuracy_score  # Model evaluation
import tensorflow as tf  # TensorFlow backend for Keras

# Load the IMDB dataset (top 10,000 frequent words)
(X_train, y_train), (X_test, y_test) = imdb.load_data(num_words=10000)

# Merge train and test data for custom shuffling and splitting
data = np.concatenate((X_train, X_test), axis=0)
labels = np.concatenate((y_train, y_test), axis=0)

# One-hot encode sequences into 10,000-dimensional binary vectors
def vectorize(sequences, dimension=10000):
    results = np.zeros((len(sequences), dimension))  # Create all-zero matrix
    for i, sequence in enumerate(sequences):
        results[i, sequence] = 1  # Set indices of present words to 1
    return results

data = vectorize(data)
labels = labels.astype("float32")

# Split dataset into training and test sets (80/20)
X_train, X_test, y_train, y_test = train_test_split(data, labels, test_size=0.2, random_state=1)

# Basic Exploratory Data Analysis
print("Number of categories:", np.unique(labels))
print("Number of unique words:", len(np.unique(np.hstack([x for x in imdb.load_data(num_words=10000)[0][0]]))))
review_lengths = [len(x) for x in imdb.load_data(num_words=10000)[0][0]]
print("Avg. review length:", np.mean(review_lengths))

# Plot class distribution
sns.set(color_codes=True)
sns.countplot(x=pd.Series(labels).map(int))
plt.title("Distribution of Labels")
plt.show()

# Define the Neural Network model
model = models.Sequential([
    layers.Dense(50, activation="relu", input_shape=(10000,)),  # Input layer
    layers.Dropout(0.3),  # Dropout for regularization
    layers.Dense(50, activation="relu"),  # Hidden layer
    layers.Dropout(0.2),  # Another dropout
    layers.Dense(50, activation="relu"),  # Another hidden layer
    layers.Dense(1, activation="sigmoid")  # Output layer for binary classification
])

# Display model summary
model.summary()

# Define early stopping to stop training when validation loss doesn't improve
early_stopping = tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3)

# Compile the model with optimizer, loss function, and evaluation metric
model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])

# Train the model on the training set
history = model.fit(
    X_train, y_train,
    epochs=10,
    batch_size=500,
    validation_data=(X_test, y_test),
    callbacks=[early_stopping]
)

# Predict on test data (convert probabilities to class labels)
predictions = (model.predict(X_test) > 0.5).astype("int32")
print("Test Accuracy:", accuracy_score(y_test, predictions))

# Plot training and validation accuracy per epoch
plt.plot(history.history['accuracy'], label='Train Accuracy')
plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
plt.title('Model Accuracy')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.legend()
plt.show()

# Plot training and validation loss per epoch
plt.plot(history.history['loss'], label='Train Loss')
plt.plot(history.history['val_loss'], label='Validation Loss')
plt.title('Model Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()
plt.show()
