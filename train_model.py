import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import os
import importlib.util

# Core Scikit-learn Tools (Preprocessing and Metrics)
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.preprocessing import LabelEncoder
# Optional dependency: bayes_opt (BayesianOptimization)
_bayes_opt_available = importlib.util.find_spec("bayes_opt") is not None
BayesianOptimization = None  # type: ignore
if _bayes_opt_available:  # pragma: no cover - environment-dependent
    # Import dynamically to avoid static linter warnings if not installed
    import importlib
    BayesianOptimization = importlib.import_module("bayes_opt").BayesianOptimization  # type: ignore

# =======================================================
# DATA LOADING, PREVIEW, AND CLEANING (Corrected for VS Code)
# =======================================================

# NOTE: Ensure the dataset file is in your project root folder.
# Prefer the new 'loan_eligibility_dataset_1.xlsx' if present; fallback to 'loan_eligibility_dataset.xlsx'.
_PREFERRED_DATASET = 'loan_eligibility_dataset_1.xlsx'
_FALLBACK_DATASET = 'loan_eligibility_dataset.xlsx'

dataset_path = _PREFERRED_DATASET if os.path.exists(_PREFERRED_DATASET) else _FALLBACK_DATASET

try:
    df = pd.read_excel(dataset_path)
except FileNotFoundError:
    print("Error: Dataset file not found. Expected one of:")
    print(f" - {_PREFERRED_DATASET}")
    print(f" - {_FALLBACK_DATASET}")
    print("Please ensure one of these files is in the same directory as this script.")
    exit()

# Dropping non-predictive columns identified in the output
# We remove 'id' and 'applicant_name' as they are unique identifiers, not predictive features.
df_xgb = df.copy().drop(columns=['id', 'applicant_name']).dropna()

# Encode categorical columns (The LabelEncoder logic works fine)
label_encoders = {}
for col in df_xgb.select_dtypes(include=['object']).columns:
    le = LabelEncoder()
    df_xgb[col] = le.fit_transform(df_xgb[col])
    label_encoders[col] = le

# Separate features and target (The target is now loan_status, encoded to 0/1)
X = df_xgb.drop(columns=['eligibility_score', 'loan_status']) # Drop the continuous score and the target label
y = df_xgb['loan_status'] # Use the encoded loan_status as the target

# Convert continuous/fractional target into discrete classes (Keeping your original logic for final target)
y = y.round().astype(int)

# Remove rare classes (Keeping your original logic for safety, though unlikely after dropna)
counts = y.value_counts()
rare_classes = counts[counts < 2].index
mask = ~y.isin(rare_classes)
X = X[mask]
y = y[mask]

# Train-test split with stratification
X_temp, X_test, y_temp, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
X_train, X_val, y_train, y_val = train_test_split(
    X_temp, y_temp, test_size=0.25, random_state=42, stratify=y_temp
)

# =======================================================
# BAYESIAN OPTIMIZATION LOGIC
# =======================================================

def xgb_objective(max_depth, learning_rate, n_estimators, gamma, subsample):
    # Cast float values to integer where required
    max_depth = int(max_depth)
    n_estimators = int(n_estimators)

    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        gamma=gamma,
        subsample=subsample,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss' 
    )

    # Use cross-validation on the X_train set
    roc_auc = cross_val_score(
        model, 
        X_train, y_train, 
        cv=3, 
        scoring='roc_auc'
    ).mean()

    return roc_auc 

# Define Hyperparameter Bounds (keeping your ranges)
pbounds = {
    'max_depth': (3, 10),
    'learning_rate': (0.01, 0.3),
    'n_estimators': (100, 500),
    'gamma': (0.0, 1.0),
    'subsample': (0.5, 1.0)
}

# Initialize and Run Optimization (optional if bayes_opt is installed)
optimizer = None
if BayesianOptimization is not None:
    optimizer = BayesianOptimization(
        f=xgb_objective,
        pbounds=pbounds,
        random_state=42,
        verbose=0
    )

# optimizer.maximize(init_points=5, n_iter=20) # Commented out to run final model immediately, assuming optimization is done

# =======================================================
# FINAL MODEL TRAINING AND EVALUATION (Using your best parameters)
# =======================================================

# 1. Define the BEST Hyperparameters found by the optimizer (rounding values)
tuned_params = {
    'max_depth': 10,
    'n_estimators': 107, 
    'learning_rate': 0.1618, 
    'gamma': 0.3961,        
    'subsample': 0.9511
}

# 2. Initialize the Final XGBoost Classifier
final_model = xgb.XGBClassifier(
    **tuned_params, 
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss' 
)

# 3. Train the model on the full Training + Validation data
X_train_full = pd.concat([X_train, X_val])
y_train_full = pd.concat([y_train, y_val])

final_model.fit(X_train_full, y_train_full)

# 4. Predict on the untouched Test Set
y_pred_tuned = final_model.predict(X_test)

# 5. Evaluate Final Accuracy and Report
final_accuracy = accuracy_score(y_test, y_pred_tuned)

print("\n" * 2)
print("="*60)
print("ML PIPELINE COMPLETE")
print("============================================================")
print(f"Final Tuned Model Accuracy on Test Set: {final_accuracy:.4f}")
print("============================================================")
print("Final Classification Report on Test Set:")
print(classification_report(y_test, y_pred_tuned))

# 6. Serialize (Save) the Final Model for Deployment
joblib.dump(final_model, 'final_xgboost_loan_model.joblib')
print("\nModel saved successfully as 'final_xgboost_loan_model.joblib' for deployment.")