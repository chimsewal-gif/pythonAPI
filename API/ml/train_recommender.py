"""
Train the programme recommendation model using real past admission data
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, roc_auc_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def load_past_admission_data(excel_path=None):
    """
    Load past admission data from Excel file
    
    Expected columns in the Excel file:
    - programme_id / programme_name
    - student_msce_points / total_points
    - subjects_count
    - english_grade, math_grade, science_grade
    - admission_status (1 = admitted, 0 = not admitted)
    - year_of_admission
    """
    
    if excel_path is None:
        # Try to find the Excel file in common locations
        possible_paths = [
            Path(__file__).parent / 'past_admission_data.xlsx',
            Path(__file__).parent.parent / 'past_admission_data.xlsx',
            Path(__file__).parent.parent.parent / 'past_admission_data.xlsx',
            Path('/run/media/lewin/DATA/fourthyear-project/API/API/ml/past_admission_data.xlsx'),
        ]
        for path in possible_paths:
            if path.exists():
                excel_path = str(path)
                break
    
    if not excel_path or not Path(excel_path).exists():
        raise FileNotFoundError(f"Past admission data Excel file not found. Please ensure 'past_admission_data.xlsx' exists in the API/ml/ directory")
    
    print(f"📊 Loading past admission data from: {excel_path}")
    
    try:
        # Try to read Excel file
        df = pd.read_excel(excel_path, sheet_name=0)
        print(f"✅ Loaded {len(df)} past admission records")
        
        # Display column names for verification
        print(f"\n📋 Available columns: {list(df.columns)}")
        
        # Check for required columns and map them
        required_mappings = {
            'programme_id': ['programme_id', 'programme', 'programme_id', 'program_code'],
            'programme_name': ['programme_name', 'programme', 'name', 'program'],
            'total_points': ['total_points', 'points', 'msce_points', 'aggregate_points'],
            'subjects_count': ['subjects_count', 'num_subjects', 'subject_count', 'credits'],
            'admission_status': ['admission_status', 'status', 'admitted', 'accepted', 'result'],
            'year': ['year', 'admission_year', 'year_of_admission', 'academic_year']
        }
        
        column_mapping = {}
        for target, possible_names in required_mappings.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    column_mapping[target] = col
                    break
        
        print(f"\n📌 Column mapping detected: {column_mapping}")
        
        # Create a clean dataframe with standard column names
        clean_df = pd.DataFrame()
        
        if 'programme_id' in column_mapping:
            clean_df['programme_id'] = df[column_mapping['programme_id']]
        elif 'programme_name' in column_mapping:
            # Encode programme names to IDs
            le = LabelEncoder()
            clean_df['programme_id'] = le.fit_transform(df[column_mapping['programme_name']].astype(str))
        else:
            raise ValueError("Could not find programme identifier column (programme_id or programme_name)")
        
        if 'total_points' in column_mapping:
            clean_df['total_points'] = pd.to_numeric(df[column_mapping['total_points']], errors='coerce')
        else:
            # Try to calculate from subject grades if available
            grade_cols = [col for col in df.columns if 'grade' in col.lower() or 'score' in col.lower()]
            if grade_cols:
                clean_df['total_points'] = df[grade_cols].sum(axis=1)
            else:
                raise ValueError("Could not find points or grades column")
        
        if 'subjects_count' in column_mapping:
            clean_df['subjects_count'] = pd.to_numeric(df[column_mapping['subjects_count']], errors='coerce')
        else:
            # Count non-null subject columns
            subject_cols = [col for col in df.columns if 'subject' in col.lower() or 'grade' in col.lower()]
            if subject_cols:
                clean_df['subjects_count'] = df[subject_cols].notna().sum(axis=1)
            else:
                clean_df['subjects_count'] = 6  # Default value
        
        if 'admission_status' in column_mapping:
            status_col = df[column_mapping['admission_status']]
            # Convert to binary (1 = admitted, 0 = not admitted)
            if status_col.dtype == 'object':
                clean_df['eligible'] = status_col.astype(str).str.lower().map(
                    lambda x: 1 if x in ['admitted', 'accepted', 'approved', 'yes', 'true', '1', 'admit'] else 0
                ).fillna(0)
            else:
                clean_df['eligible'] = (status_col == 1).astype(int)
        else:
            raise ValueError("Could not find admission status column")
        
        if 'year' in column_mapping:
            clean_df['year'] = df[column_mapping['year']]
        
        # Drop rows with NaN values
        initial_count = len(clean_df)
        clean_df = clean_df.dropna()
        print(f"\n🧹 Dropped {initial_count - len(clean_df)} rows with missing values")
        
        # Add derived features
        clean_df['points_per_subject'] = clean_df['total_points'] / clean_df['subjects_count']
        clean_df['above_min_credits'] = (clean_df['subjects_count'] >= 6).astype(int)
        clean_df['points_within_limit'] = (clean_df['total_points'] <= 30).astype(int)
        
        print(f"\n📊 Final dataset shape: {clean_df.shape}")
        print(f"📊 Admitted count: {clean_df['eligible'].sum()}")
        print(f"📊 Not admitted count: {len(clean_df) - clean_df['eligible'].sum()}")
        
        return clean_df
        
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        raise

def train_model(excel_path=None):
    """Train and save the recommendation model using real past admission data"""
    
    print("=" * 60)
    print("🎓 PROGRAMME RECOMMENDATION MODEL TRAINING")
    print("=" * 60)
    
    # Load real past admission data
    print("\n📂 Loading past admission data...")
    try:
        df = load_past_admission_data(excel_path)
    except FileNotFoundError as e:
        print(f"\n⚠️ {e}")
        print("\n📋 Please create an Excel file with the following structure:")
        print("""
        Required columns (at minimum):
        - programme_id (or programme_name) - The programme the student applied to
        - total_points (or individual subject grades) - Student's MSCE total points
        - subjects_count - Number of MSCE subjects taken
        - admission_status - Whether the student was admitted (1/0 or Admitted/Rejected)
        
        Optional but recommended:
        - english_grade, math_grade, science_grade - Individual subject grades
        - year - Year of admission
        - student_background - Any additional information
        """)
        return None
    
    # Prepare features
    feature_columns = ['programme_id', 'subjects_count', 'total_points', 'points_per_subject', 
                       'above_min_credits', 'points_within_limit']
    
    # Use available features
    available_features = [col for col in feature_columns if col in df.columns]
    X = df[available_features]
    y = df['eligible']
    
    print(f"\n🎯 Features used: {available_features}")
    print(f"🎯 Target: Admission Status")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n📊 Training set size: {len(X_train)}")
    print(f"📊 Test set size: {len(X_test)}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Hyperparameter tuning
    print("\n🔧 Performing hyperparameter tuning...")
    param_grid = {
        'n_estimators': [100, 200, 300],
        'max_depth': [5, 10, 15, None],
        'min_samples_split': [2, 5, 10],
        'min_samples_leaf': [1, 2, 4],
        'class_weight': ['balanced', None]
    }
    
    base_model = RandomForestClassifier(random_state=42)
    grid_search = GridSearchCV(base_model, param_grid, cv=5, scoring='roc_auc', n_jobs=-1, verbose=1)
    grid_search.fit(X_train_scaled, y_train)
    
    model = grid_search.best_estimator_
    print(f"\n✅ Best parameters: {grid_search.best_params_}")
    
    # Train the final model
    print("\n🚀 Training final model...")
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    
    print("\n" + "=" * 60)
    print("📈 MODEL PERFORMANCE METRICS")
    print("=" * 60)
    print(f"✅ Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"✅ ROC-AUC Score: {roc_auc:.4f}")
    print(f"✅ Best Parameters: {grid_search.best_params_}")
    
    print("\n📋 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Not Eligible', 'Eligible']))
    
    print("\n📊 Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(f"   True Negatives: {cm[0,0]} | False Positives: {cm[0,1]}")
    print(f"   False Negatives: {cm[1,0]} | True Positives: {cm[1,1]}")
    
    # Feature importance
    print("\n🔍 Feature Importance:")
    feature_importance = pd.DataFrame({
        'feature': available_features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for idx, row in feature_importance.iterrows():
        print(f"   {row['feature']}: {row['importance']:.4f}")
    
    # Cross-validation score
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring='accuracy')
    print(f"\n📊 Cross-validation accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Save model and scaler
    print("\n💾 Saving model...")
    model_path = os.path.join(os.path.dirname(__file__), 'programme_recommender_model.pkl')
    scaler_path = os.path.join(os.path.dirname(__file__), 'programme_recommender_scaler.pkl')
    
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    print(f"✅ Model saved to: {model_path}")
    print(f"✅ Scaler saved to: {scaler_path}")
    
    # Save feature list as well
    features_path = os.path.join(os.path.dirname(__file__), 'programme_recommender_features.pkl')
    with open(features_path, 'wb') as f:
        pickle.dump(available_features, f)
    
    print(f"✅ Features list saved to: {features_path}")
    
    # Return model info
    return {
        'model': model,
        'scaler': scaler,
        'features': available_features,
        'accuracy': accuracy,
        'roc_auc': roc_auc,
        'best_params': grid_search.best_params_,
        'feature_importance': feature_importance.to_dict('records'),
        'training_size': len(X_train),
        'test_size': len(X_test)
    }

def predict_eligibility(programme_id, subjects_count, total_points, scaler, model, features):
    """Predict eligibility for a single student"""
    # Create feature vector
    points_per_subject = total_points / max(subjects_count, 1)
    above_min_credits = 1 if subjects_count >= 6 else 0
    points_within_limit = 1 if total_points <= 30 else 0
    
    feature_dict = {
        'programme_id': programme_id,
        'subjects_count': subjects_count,
        'total_points': total_points,
        'points_per_subject': points_per_subject,
        'above_min_credits': above_min_credits,
        'points_within_limit': points_within_limit
    }
    
    # Create feature vector in the correct order
    feature_vector = np.array([[feature_dict[f] for f in features]])
    
    # Scale and predict
    feature_vector_scaled = scaler.transform(feature_vector)
    probability = model.predict_proba(feature_vector_scaled)[0][1]
    prediction = model.predict(feature_vector_scaled)[0]
    
    return {
        'eligible': bool(prediction),
        'probability': float(probability),
        'features': feature_dict
    }

if __name__ == "__main__":
    # Train the model
    result = train_model()
    
    if result:
        print("\n" + "=" * 60)
        print("✅ MODEL TRAINING COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Example prediction
        print("\n📝 Example prediction:")
        example_pred = predict_eligibility(
            programme_id=1,
            subjects_count=8,
            total_points=25,
            scaler=result['scaler'],
            model=result['model'],
            features=result['features']
        )
        print(f"   Eligibility: {'Eligible' if example_pred['eligible'] else 'Not Eligible'}")
        print(f"   Probability: {example_pred['probability']*100:.2f}%")