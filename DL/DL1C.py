# Import necessary libraries
import numpy as np  # For numerical operations
import pandas as pd  # For handling datasets
from sklearn.model_selection import train_test_split  # Splitting data into train & test sets
from sklearn.linear_model import LinearRegression  # Linear Regression Model
from sklearn.preprocessing import StandardScaler  # Standardization of data
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score  # Evaluation metrics
import matplotlib.pyplot as plt  # Plotting graphs

# Importing Keras for building the neural network
from keras.models import Sequential  # Sequential model type
from keras.layers import Dense  # Dense (fully connected) layers

# Load the dataset
boston = pd.read_csv("boston_house_prices.csv")  # Load dataset into a DataFrame

# Select features and target variable
X = boston[['LSTAT', 'RM', 'PTRATIO']]  # Feature columns
y = boston['PRICE']  # Target column

# Split data into training and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=4)

# Standardize the feature data
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)  # Fit to training data
X_test_scaled = scaler.transform(X_test)  # Transform test data

# Train Linear Regression model
lr_model = LinearRegression()
lr_model.fit(X_train_scaled, y_train)

# Predict using the trained Linear Regression model
y_pred_lr = lr_model.predict(X_test_scaled)

# Evaluate the Linear Regression model
mse_lr = mean_squared_error(y_test, y_pred_lr)
mae_lr = mean_absolute_error(y_test, y_pred_lr)
r2_lr = r2_score(y_test, y_pred_lr)

# Display evaluation results
print("Linear Regression Model Evaluation:")
print(f"Mean Squared Error: {mse_lr}")
print(f"Mean Absolute Error: {mae_lr}")
print(f"R2 Score: {r2_lr}")

# Define a deep learning model (ANN)
model = Sequential([
    Dense(128, activation='relu', input_dim=3),  # Input + hidden layer
    Dense(64, activation='relu'),  # 2nd hidden layer
    Dense(32, activation='relu'),  # 3rd hidden layer
    Dense(16, activation='relu'),  # 4th hidden layer
    Dense(1)  # Output layer (price prediction)
])

# Compile the ANN model
model.compile(optimizer='adam', loss='mse', metrics=['mae'])

# Train the ANN model
history = model.fit(X_train_scaled, y_train, epochs=100, validation_split=0.05, verbose=1)

# Predict and evaluate ANN on test set
y_pred_nn = model.predict(X_test_scaled)
mse_nn, mae_nn = model.evaluate(X_test_scaled, y_test)

# Plot training loss curve
pd.DataFrame(history.history).plot(figsize=(6, 4), xlabel="Epochs", ylabel="Loss", title='Loss Curves')
plt.show()

# Display evaluation results for neural network
print("\nNeural Network Model Evaluation:")
print(f"Mean Squared Error: {mse_nn}")
print(f"Mean Absolute Error: {mae_nn}")

# Predict new data
new_data = np.array([[0.1, 10.0, 5.0]])  # New input data
new_data_scaled = scaler.transform(new_data)  # Scale new data
prediction = model.predict(new_data_scaled)  # Predict using ANN

# Display the prediction
print("\nPredicted House Price:", prediction[0][0])
