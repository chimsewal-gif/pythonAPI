import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib
import os

# Example data: [average_points]
X = np.array([
    [3], [4], [5], [6], [7], [8]
])

# 1 = admitted, 0 = rejected
y = np.array([1, 1, 1, 1, 0, 0])

model = LogisticRegression()
model.fit(X, y)

# Save model
os.makedirs("ml", exist_ok=True)
joblib.dump(model, "ml/admission_model.pkl")

print("Model saved!")