import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

NUMERIC_FEATURES = [
    "home_form_pts5", "home_goal_diff5",
    "away_form_pts5", "away_goal_diff5",
    "home_form_pts10", "home_goal_diff10",
    "away_form_pts10", "away_goal_diff10",
    "h2h_home_win_rate", "home_advantage_baseline",
]


def prepare_data(df):
    X = df[NUMERIC_FEATURES + ["league_id"]].copy()
    X = pd.get_dummies(X, columns=["league_id"], prefix="league")
    y = df["result"]
    return X, y


def evaluate(name, model, X_test, y_test, y_classes):
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n=== {name} ===")
    print(f"Accuracy: {acc:.3f}")
    print(classification_report(y_test, y_pred))
    print("Confusion matrix, labels:", y_classes)
    print(confusion_matrix(y_test, y_pred, labels=y_classes))
    return acc


def train():
    df = pd.read_csv("app/ml/features.csv")
    X, y = prepare_data(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    y_classes = sorted(y.unique())
    majority_class = y_train.value_counts().idxmax()
    baseline_acc = accuracy_score(y_test, [majority_class] * len(y_test))
    print(f"Baseline (always predict '{majority_class}') accuracy: {baseline_acc:.3f}")

    # --- Logistic Regression ---
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    log_reg = LogisticRegression(max_iter=1000, class_weight="balanced")
    log_reg.fit(X_train_scaled, y_train)
    log_reg_acc = evaluate("Logistic Regression", log_reg, X_test_scaled, y_test, y_classes)

    # --- Random Forest ---
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=6, class_weight="balanced", random_state=42
    )
    rf.fit(X_train, y_train)
    rf_acc = evaluate("Random Forest", rf, X_test, y_test, y_classes)

    # Feature importance from random forest (only meaningful model for this)
    importances = pd.Series(rf.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print("\nTop 10 feature importances (Random Forest):")
    print(importances.head(10))

    # Save whichever performed better
    if rf_acc >= log_reg_acc:
        print(f"\nRandom Forest wins ({rf_acc:.3f} vs {log_reg_acc:.3f}) - saving it as the active model")
        joblib.dump(rf, "app/ml/model.joblib")
        joblib.dump(None, "app/ml/scaler.joblib")  # RF doesn't need scaling
        joblib.dump(list(X_train.columns), "app/ml/feature_columns.joblib")
    else:
        print(f"\nLogistic Regression wins ({log_reg_acc:.3f} vs {rf_acc:.3f}) - saving it as the active model")
        joblib.dump(log_reg, "app/ml/model.joblib")
        joblib.dump(scaler, "app/ml/scaler.joblib")
        joblib.dump(list(X_train.columns), "app/ml/feature_columns.joblib")

    print("Saved to app/ml/")


if __name__ == "__main__":
    train()
