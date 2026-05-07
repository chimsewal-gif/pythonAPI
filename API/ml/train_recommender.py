"""
Train the programme recommendation model
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

def generate_training_data():
    """Generate synthetic training data for demonstration"""
    np.random.seed(42)
    
    # Programme IDs and their required subject patterns
    programme_patterns = {
        1: {'subjects': ['English'], 'min_points': 0},
        2: {'subjects': ['English'], 'min_points': 30},
        20: {'subjects': ['English', 'Mathematics', 'Chemistry', 'Physics', 'Biology'], 'min_points': 30},
        28: {'subjects': ['English', 'Mathematics', 'Physics', 'Chemistry'], 'min_points': 30},
        29: {'subjects': ['English', 'Mathematics'], 'min_points': 30},
        30: {'subjects': ['English', 'Biology', 'Mathematics'], 'min_points': 30},
    }
    
    data = []
    
    for programme_id, requirements in programme_patterns.items():
        for _ in range(100):
            # Generate random student profile
            subjects_count = np.random.randint(6, 10)
            points = np.random.randint(20, 45)
            
            # Check if eligible
            eligible = 1
            if points > requirements['min_points'] and requirements['min_points'] > 0:
                eligible = 0
            if subjects_count < 6:
                eligible = 0
            
            data.append({
                'programme_id': programme_id,
                'subjects_count': subjects_count,
                'total_points': points,
                'eligible': eligible
            })
    
    return pd.DataFrame(data)

def train_model():
    """Train and save the recommendation model"""
    print("Generating training data...")
    df = generate_training_data()
    
    features = ['programme_id', 'subjects_count', 'total_points']
    X = df[features]
    y = df['eligible']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    print("Training model...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy: {accuracy:.2f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save model
    model_path = os.path.join(os.path.dirname(__file__), 'programme_recommender_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    print(f"Model saved to {model_path}")
    return model

if __name__ == "__main__":
    train_model()