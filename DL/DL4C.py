# Import necessary libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

# Step 1: Download historical Google stock prices
df = yf.download("GOOG", start="2015-01-01", end="2023-12-31")
df = df[['Close']]  # Use only the 'Close' price
df.dropna(inplace=True)  # Remove any missing values

# Step 2: Normalize closing prices to [0, 1] range
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(df)

# Step 3: Convert to supervised learning format using past 60 days to predict the next
def create_dataset(data, time_step=60):
    X, y = [], []
    for i in range(time_step, len(data)):
        X.append(data[i-time_step:i, 0])  # previous 60 steps
        y.append(data[i, 0])  # target value
    return np.array(X), np.array(y)

time_step = 60
X, y = create_dataset(scaled_data, time_step)

# Reshape input for LSTM: [samples, time steps, features]
X = X.reshape((X.shape[0], X.shape[1], 1))

# Step 4: Split data into training and testing sets (80/20)
split = int(len(X) * 0.8)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

# Step 5: Build the LSTM model
model = Sequential()
model.add(LSTM(50, return_sequences=True, input_shape=(time_step, 1)))
model.add(Dropout(0.2))
model.add(LSTM(50, return_sequences=False))
model.add(Dropout(0.2))
model.add(Dense(1))  # Output layer
model.compile(optimizer='adam', loss='mean_squared_error')  # Regression loss
model.summary()

# Step 6: Train the model
history = model.fit(X_train, y_train, validation_data=(X_test, y_test), epochs=20, batch_size=64)

# Step 7: Make predictions on training and testing sets
train_predict = model.predict(X_train)
test_predict = model.predict(X_test)

# Step 7.1: Inverse transform predictions and labels to original scale
train_predict = scaler.inverse_transform(train_predict)
test_predict = scaler.inverse_transform(test_predict)
y_train_inv = scaler.inverse_transform(y_train.reshape(-1, 1))
y_test_inv = scaler.inverse_transform(y_test.reshape(-1, 1))

# Step 8: Plot predictions vs actual prices
plt.figure(figsize=(14,6))
plt.plot(df.index, scaler.inverse_transform(scaled_data), label='Actual Price')  # Actual price

# Define indexes for predicted values to align with original data
train_index = df.index[time_step:split+time_step]
test_index = df.index[split+time_step:]

# Plot training and testing predictions
plt.plot(train_index, train_predict, label='Train Prediction')
plt.plot(test_index, test_predict, label='Test Prediction')
plt.xlabel("Date")
plt.ylabel("Stock Price (USD)")
plt.title("Google Stock Price Prediction using RNN (LSTM)")
plt.legend()
plt.grid()
plt.show()
