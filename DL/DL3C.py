# Import necessary libraries
import tensorflow as tf
import matplotlib.pyplot as plt
from tensorflow import keras
import numpy as np
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report

# Load Fashion MNIST dataset (images and labels)
(x_train, y_train), (x_test, y_test) = keras.datasets.fashion_mnist.load_data()

# Normalize the pixel values to range [0, 1]
x_train = x_train.astype('float32') / 255.0
x_test = x_test.astype('float32') / 255.0

# Reshape data for CNN: add channel dimension (grayscale = 1 channel)
x_train = x_train.reshape(-1, 28, 28, 1)
x_test = x_test.reshape(-1, 28, 28, 1)

# Define the CNN architecture
model = keras.Sequential([
    keras.layers.Conv2D(32, (3,3), activation='relu', input_shape=(28,28,1)),  # First conv layer
    keras.layers.MaxPooling2D((2,2)),  # Downsample
    keras.layers.Dropout(0.25),  # Regularization
    keras.layers.Conv2D(64, (3,3), activation='relu'),  # Second conv layer
    keras.layers.MaxPooling2D((2,2)),
    keras.layers.Dropout(0.25),
    keras.layers.Conv2D(128, (3,3), activation='relu'),  # Third conv layer
    keras.layers.Flatten(),  # Flatten output for dense layers
    keras.layers.Dense(128, activation='relu'),  # Fully connected layer
    keras.layers.Dropout(0.25),
    keras.layers.Dense(10, activation='softmax')  # Output layer for 10 classes
])

# Compile the model with optimizer, loss, and metric
model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

# Train the model for 10 epochs
history = model.fit(x_train, y_train, epochs=10, validation_data=(x_test, y_test))

# Evaluate on test set
test_loss, test_acc = model.evaluate(x_test, y_test)
print('Test accuracy:', test_acc)

# Define label names for visualization
class_names = ['T-shirt/top', 'Trouser', 'Pullover', 'Dress', 'Coat',
               'Sandal', 'Shirt', 'Sneaker', 'Bag', 'Ankle boot']

# Make predictions on test set
predictions = model.predict(x_test)
predicted_labels = np.argmax(predictions, axis=1)

# Show predictions vs actual for the first 10 images
plt.figure(figsize=(12, 12))
for i in range(10):
    plt.subplot(5, 5, i + 1)
    plt.xticks([])
    plt.yticks([])
    plt.grid(False)
    plt.imshow(x_test[i].reshape(28, 28), cmap=plt.cm.binary)
    true_label = class_names[y_test[i]]
    pred_label = class_names[predicted_labels[i]]
    color = 'green' if predicted_labels[i] == y_test[i] else 'red'
    plt.xlabel(f"True: {true_label}\nPred: {pred_label}", color=color)
plt.tight_layout()
plt.show()

# Generate confusion matrix
cm = confusion_matrix(y_test, predicted_labels)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
plt.title("Confusion Matrix")
plt.xlabel("Predicted Label")
plt.ylabel("True Label")
plt.show()

# Print classification report
print("Classification Report:\n")
print(classification_report(y_test, predicted_labels, target_names=class_names))
