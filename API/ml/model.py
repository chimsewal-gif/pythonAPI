import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "admission_model.pkl")

model = joblib.load(MODEL_PATH)

def predict_admission(avg_points):
    prediction = model.predict([[avg_points]])[0]
    probability = model.predict_proba([[avg_points]])[0][1]

    return prediction, probability