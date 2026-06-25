import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

NUMERIC_FEATURES = [
    "home_form_pts", "home_gf", "home_ga", "home_btts_rate", "home_over25_rate",
    "away_form_pts", "away_gf", "away_ga", "away_btts_rate", "away_over25_rate",
]


def prepare_data(df, target_col):
    X = df[NUMERIC_FEATURES + ["league_id"]].copy()
    X = pd.get_dummies(X, columns=["league_id"], prefix="league")
    y = df[target_col]
    return X, y


def train_binary_model(df, target_col, model_name):
    print(f"\n{'='*50}")
    print(f"Training: {model_name}")
    print(f"{'='*50}")

    X, y = prepare_data(df, target_col)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    majority = y_train.value_counts().idxmax()
    baseline_acc = accuracy_score(y_test, [majority] * len(y_test))
    print(f"Baseline (always predict {majority}): {baseline_acc:.3f}")

    model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"Model accuracy: {acc:.3f}")
    print(classification_report(y_test, y_pred))

    importances = pd.Series(model.feature_importances_, index=X_train.columns).sort_values(ascending=False)
    print("Top 5 features:")
    print(importances.head(5))

    joblib.dump(model, f"app/ml/{model_name}_model.joblib")
    joblib.dump(list(X_train.columns), f"app/ml/{model_name}_feature_columns.joblib")
    print(f"Saved app/ml/{model_name}_model.joblib")

    return acc, baseline_acc


if __name__ == "__main__":
    df = pd.read_csv("app/ml/btts_ou_features.csv")

    btts_acc, btts_baseline = train_binary_model(df, "btts", "btts")
    over25_acc, over25_baseline = train_binary_model(df, "over25", "over25")

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"BTTS:      {btts_acc:.3f} vs baseline {btts_baseline:.3f} (+{(btts_acc-btts_baseline)*100:.1f}pts)")
    print(f"Over 2.5:  {over25_acc:.3f} vs baseline {over25_baseline:.3f} (+{(over25_acc-over25_baseline)*100:.1f}pts)")
