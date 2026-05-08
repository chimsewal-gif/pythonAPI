"""
Train the Admission Prediction Model using real past admission data
This model predicts admission probability based on MSCE results and other factors
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, classification_report
import joblib
import os
import warnings
from pathlib import Path
import json
warnings.filterwarnings('ignore')

def load_past_admission_data(excel_path=None):
    """
    Load past admission data from Excel file
    """
    if excel_path is None:
        # Try to find the Excel file in common locations
        possible_paths = [
            Path(__file__).parent / 'past_admission_data.xlsx',
            Path(__file__).parent.parent / 'past_admission_data.xlsx',
            Path(__file__).parent.parent.parent / 'past_admission_data.xlsx',
            Path('past_admission_data.xlsx'),
        ]
        for path in possible_paths:
            if path.exists():
                excel_path = str(path)
                break
    
    if not excel_path or not Path(excel_path).exists():
        print(f"\n⚠️ Past admission data Excel file not found at: {excel_path}")
        return None
    
    print(f"📊 Loading past admission data from: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path)
        print(f"✅ Loaded {len(df)} past admission records")
        print(f"\n📋 Columns found: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return None

def preprocess_data(df):
    """
    Preprocess the data and create features
    """
    # Define feature columns with possible column name variations
    column_mapping = {
        'subjects_count': ['subjects_count', 'num_subjects', 'subject_count', 'credits', 'num_credits'],
        'total_points': ['total_points', 'points', 'msce_points', 'aggregate_points'],
        'programme_id': ['programme_id', 'program_id', 'program'],
        'eligible': ['eligible', 'admitted', 'admission_status', 'status', 'accepted', 'result']
    }
    
    # Create clean dataframe
    clean_df = pd.DataFrame()
    feature_columns = []
    
    # Map columns
    for target, possible_names in column_mapping.items():
        found = False
        for col in df.columns:
            if col.lower() in [name.lower() for name in possible_names]:
                clean_df[target] = df[col]
                if target != 'eligible':  # Don't add target to features
                    feature_columns.append(target)
                found = True
                print(f"   Mapped '{col}' -> '{target}'")
                break
        
        # Handle missing columns
        if not found:
            if target == 'subjects_count':
                clean_df[target] = 6  # Default
                feature_columns.append(target)
                print(f"   Using default for '{target}': 6")
            elif target == 'total_points':
                # Try to calculate from average points if available
                if 'average_points' in df.columns:
                    clean_df[target] = df['average_points'] * clean_df['subjects_count']
                else:
                    clean_df[target] = 30  # Default
                feature_columns.append(target)
                print(f"   Using default for '{target}': 30")
            elif target == 'programme_id':
                clean_df[target] = 1  # Default
                feature_columns.append(target)
                print(f"   Using default for '{target}': 1")
            elif target == 'eligible':
                raise ValueError(f"Required column '{target}' (or admitted/admission_status) not found in data")
    
    # Calculate derived features
    clean_df['points_per_subject'] = clean_df['total_points'] / clean_df['subjects_count']
    feature_columns.append('points_per_subject')
    
    clean_df['above_min_credits'] = (clean_df['subjects_count'] >= 6).astype(int)
    feature_columns.append('above_min_credits')
    
    clean_df['points_within_limit'] = (clean_df['total_points'] <= 30).astype(int)
    feature_columns.append('points_within_limit')
    
    # Ensure eligible is integer
    if clean_df['eligible'].dtype == 'object':
        clean_df['eligible'] = clean_df['eligible'].astype(str).str.lower().map(
            lambda x: 1 if x in ['1', 'yes', 'true', 'admitted', 'eligible', 'accepted'] else 0
        ).fillna(0)
    else:
        clean_df['eligible'] = clean_df['eligible'].astype(int)
    
    # Drop rows with NaN values
    initial_count = len(clean_df)
    clean_df = clean_df.dropna()
    
    if initial_count > len(clean_df):
        print(f"\n🧹 Dropped {initial_count - len(clean_df)} rows with missing values")
    
    print(f"\n🎯 Features to use: {feature_columns}")
    print(f"🎯 Target: eligible (admission status)")
    print(f"📊 Positive samples (admitted): {clean_df['eligible'].sum()}")
    print(f"📊 Negative samples (not admitted): {len(clean_df) - clean_df['eligible'].sum()}")
    
    return clean_df, feature_columns

def train_model():
    """
    Train the admission prediction model
    """
    print("=" * 60)
    print("🎓 ADMISSION PREDICTION MODEL TRAINING")
    print("=" * 60)
    
    # Load data
    print("\n📂 Loading past admission data...")
    df = load_past_admission_data()
    
    if df is None:
        print("❌ Failed to load data. Exiting.")
        return None
    
    # Preprocess data
    print("\n🔄 Preprocessing data...")
    clean_df, feature_columns = preprocess_data(df)
    
    if clean_df is None or len(clean_df) == 0:
        print("❌ No valid data after preprocessing.")
        return None
    
    # Prepare features and target
    X = clean_df[feature_columns]
    y = clean_df['eligible']
    
    print(f"\n📊 Final dataset shape: {X.shape}")
    print(f"📊 Admitted count: {y.sum()}")
    print(f"📊 Not admitted count: {len(y) - y.sum()}")
    print(f"📊 Admission rate: {y.mean()*100:.2f}%")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n📊 Training set: {len(X_train)} samples")
    print(f"📊 Test set: {len(X_test)} samples")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Try multiple models and select the best
    print("\n🔍 Testing different models...")
    
    models = {
        'Logistic Regression': LogisticRegression(max_iter=1000, random_state=42),
        'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, random_state=42)
    }
    
    best_model = None
    best_accuracy = 0
    best_model_name = ""
    best_roc_auc = 0
    
    for name, model in models.items():
        # Train
        model.fit(X_train_scaled, y_train)
        
        # Predict
        y_pred = model.predict(X_test_scaled)
        y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
        
        accuracy = accuracy_score(y_test, y_pred)
        roc_auc = roc_auc_score(y_test, y_pred_proba)
        
        print(f"   {name}: Accuracy = {accuracy:.4f}, ROC-AUC = {roc_auc:.4f}")
        
        if roc_auc > best_roc_auc:
            best_roc_auc = roc_auc
            best_accuracy = accuracy
            best_model = model
            best_model_name = name
    
    print(f"\n✅ Best model: {best_model_name} with Accuracy: {best_accuracy:.4f}, ROC-AUC: {best_roc_auc:.4f}")
    
    # Hyperparameter tuning for the best model type
    print("\n🔧 Performing hyperparameter tuning...")
    
    if best_model_name == 'Random Forest':
        param_grid = {
            'n_estimators': [100, 200],
            'max_depth': [10, 15, None],
            'min_samples_split': [2, 5],
            'class_weight': ['balanced', None]
        }
        base_model = RandomForestClassifier(random_state=42)
    elif best_model_name == 'Gradient Boosting':
        param_grid = {
            'n_estimators': [100, 200],
            'learning_rate': [0.05, 0.1],
            'max_depth': [3, 5]
        }
        base_model = GradientBoostingClassifier(random_state=42)
    else:
        param_grid = {
            'C': [0.1, 1, 10],
            'penalty': ['l2'],
            'solver': ['lbfgs']
        }
        base_model = LogisticRegression(max_iter=1000, random_state=42)
    
    grid_search = GridSearchCV(base_model, param_grid, cv=5, scoring='roc_auc', n_jobs=-1)
    grid_search.fit(X_train_scaled, y_train)
    
    final_model = grid_search.best_estimator_
    print(f"✅ Best parameters: {grid_search.best_params_}")
    
    # Evaluate final model
    y_pred = final_model.predict(X_test_scaled)
    y_pred_proba = final_model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    
    print("\n" + "=" * 60)
    print("📈 MODEL PERFORMANCE METRICS")
    print("=" * 60)
    print(f"✅ Accuracy:  {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"✅ Precision: {precision:.4f}")
    print(f"✅ Recall:    {recall:.4f}")
    print(f"✅ F1 Score:  {f1:.4f}")
    print(f"✅ ROC-AUC:   {roc_auc:.4f}")
    
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Not Admitted', 'Admitted']))
    
    print("\n📊 Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"   True Negatives:  {cm[0,0]} | False Positives: {cm[0,1]}")
    print(f"   False Negatives: {cm[1,0]} | True Positives:  {cm[1,1]}")
    
    # Feature importance
    if hasattr(final_model, 'feature_importances_'):
        print("\n🔍 Feature Importance:")
        feature_importance = pd.DataFrame({
            'feature': feature_columns,
            'importance': final_model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        for idx, row in feature_importance.iterrows():
            print(f"   {row['feature']}: {row['importance']:.4f}")
    elif hasattr(final_model, 'coef_'):
        print("\n🔍 Feature Coefficients:")
        coefficients = pd.DataFrame({
            'feature': feature_columns,
            'coefficient': final_model.coef_[0]
        }).sort_values('coefficient', ascending=False)
        
        for idx, row in coefficients.iterrows():
            print(f"   {row['feature']}: {row['coefficient']:.4f}")
    
    # Cross-validation score
    cv_scores = cross_val_score(final_model, X_train_scaled, y_train, cv=5, scoring='accuracy')
    print(f"\n📊 Cross-validation accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Save model
    print("\n💾 Saving model...")
    
    # Create ml directory if it doesn't exist
    ml_dir = Path(__file__).parent / 'models'
    ml_dir.mkdir(exist_ok=True)
    
    model_path = ml_dir / 'admission_model.pkl'
    scaler_path = ml_dir / 'admission_scaler.pkl'
    features_path = ml_dir / 'admission_features.pkl'
    
    joblib.dump(final_model, model_path)
    joblib.dump(scaler, scaler_path)
    joblib.dump(feature_columns, features_path)
    
    print(f"✅ Model saved to: {model_path}")
    print(f"✅ Scaler saved to: {scaler_path}")
    print(f"✅ Features saved to: {features_path}")
    
    # Save model info
    model_info = {
        'model_type': best_model_name,
        'accuracy': accuracy,
        'roc_auc': roc_auc,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'features': feature_columns,
        'training_samples': int(len(X_train)),
        'test_samples': int(len(X_test))
    }
    
    info_path = ml_dir / 'admission_model_info.json'
    with open(info_path, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    print(f"✅ Model info saved to: {info_path}")
    
    return {
        'model': final_model,
        'scaler': scaler,
        'features': feature_columns,
        'metrics': model_info
    }

def predict_admission(features_dict, model=None, scaler=None, feature_columns=None):
    """
    Predict admission probability for a new applicant
    """
    if model is None or scaler is None or feature_columns is None:
        # Load saved model
        ml_dir = Path(__file__).parent / 'models'
        model = joblib.load(ml_dir / 'admission_model.pkl')
        scaler = joblib.load(ml_dir / 'admission_scaler.pkl')
        feature_columns = joblib.load(ml_dir / 'admission_features.pkl')
    
    # Create feature vector
    feature_vector = np.array([[features_dict.get(col, 0) for col in feature_columns]])
    
    # Scale features
    feature_vector_scaled = scaler.transform(feature_vector)
    
    # Predict
    probability = model.predict_proba(feature_vector_scaled)[0][1]
    prediction = model.predict(feature_vector_scaled)[0]
    
    return {
        'admitted': bool(prediction),
        'probability': float(probability),
        'recommendation': 'Admit' if probability >= 0.5 else 'Review',
        'confidence': abs(probability - 0.5) * 2
    }

if __name__ == "__main__":
    # Train the model
    result = train_model()
    
    if result:
        print("\n" + "=" * 60)
        print("✅ MODEL TRAINING COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Test prediction example
        print("\n📝 Example prediction for a new student:")
        example_features = {
            'subjects_count': 8,
            'total_points': 25,
            'programme_id': 1,
            'points_per_subject': 3.125,
            'above_min_credits': 1,
            'points_within_limit': 1
        }
        
        prediction = predict_admission(example_features)
        print(f"   Subjects Count: {example_features['subjects_count']}")
        print(f"   Total Points: {example_features['total_points']}")
        print(f"   Admission Probability: {prediction['probability']*100:.2f}%")
        print(f"   Recommendation: {prediction['recommendation']}")
    else:
        print("\n❌ Training failed. Please check your data.")