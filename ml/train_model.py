#!/usr/bin/env python3
"""
Retrains the fair-price model from the current database and saves it.

Same logic as train_model.ipynb (pull -> dedupe -> feature engineer ->
train on log(price) -> evaluate -> compute fair price/deal score), but as
a script so it can run unattended as part of the daily automation. The
notebook stays for manual/interactive exploration; this is the
"production" version that keeps the saved model fresh automatically.

Deal scores are computed from out-of-fold (K-fold cross-validated)
predictions, not from a model predicting on rows it was trained on --
with a high-cardinality categorical like `model`, an in-sample prediction
is close to memorized, which pinned nearly every listing at a ~100
score regardless of actual price. Each row's predicted_price instead
comes from a fold that never saw that row during training. The MAPE/RMSE
reported here are computed the same way, across all folds. A final model
fit on 100% of the data is what actually gets saved to disk.

Safety: if a retrain's MAPE is much worse than the last recorded one
(>50% relatively worse), the new model/results are NOT saved over the
working ones -- only logged as a flagged anomaly in accuracy_history.csv.
This stops one bad day of scraped data from silently degrading the
"live" model.
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import psycopg2
import xgboost as xgb
from dotenv import load_dotenv
from sklearn.metrics import mean_absolute_percentage_error, root_mean_squared_error
from sklearn.model_selection import KFold

load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set (check your .env file)")
    sys.exit(1)

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ML_DIR, "fair_price_model.json")
RESULTS_PATH = os.path.join(ML_DIR, "model_results.csv")
HISTORY_PATH = os.path.join(ML_DIR, "accuracy_history.csv")

DEGRADATION_THRESHOLD = 1.5  # new MAPE > 1.5x last MAPE = flagged, not promoted
N_SPLITS = 5  # folds for out-of-fold deal-score predictions


def parse_storage(val):
    if pd.isna(val):
        return None
    m = re.search(r"(\d+)", str(val))
    return int(m.group(1)) if m else None


def extract_city(val):
    if pd.isna(val):
        return None
    return str(val).split(",")[0].strip()


def load_last_mape():
    if not os.path.exists(HISTORY_PATH):
        return None
    with open(HISTORY_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    promoted = [r for r in rows if r.get("promoted") == "True"]
    return float(promoted[-1]["mape_pct"]) if promoted else None


def append_history(row):
    is_new = not os.path.exists(HISTORY_PATH)
    with open(HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def write_predictions(conn, model_df):
    """Writes predicted_price/fair_price_min/fair_price_max/deal_score onto
    the *latest* phones_normalized row for each url — this is what "current
    listing" means for the API, deployed separately from the scraping Mac,
    to serve directly from Postgres without needing the model file itself."""
    with conn.cursor() as cur:
        for _, row in model_df.iterrows():
            cur.execute(
                """
                UPDATE phones_normalized
                SET predicted_price = %s, fair_price_min = %s,
                    fair_price_max = %s, deal_score = %s
                WHERE listing_id = %s
                """,
                (
                    row["predicted_price"],
                    row["fair_price_min"],
                    row["fair_price_max"],
                    row["deal_score"],
                    int(row["listing_id"]),
                ),
            )
    conn.commit()


def main():
    conn = psycopg2.connect(DATABASE_URL)
    query = """
        SELECT DISTINCT ON (l.url)
            l.id AS listing_id, l.url, l.price, l.location, l.photo_count, l.seller_type,
            n.brand, n.model, n.storage, n.condition_clean
        FROM listings l
        JOIN phones_normalized n ON n.listing_id = l.id
        ORDER BY l.url, l.scraped_date DESC
    """
    df = pd.read_sql(query, conn)

    df["storage_gb"] = df["storage"].apply(parse_storage)
    df["city"] = df["location"].apply(extract_city)

    model_df = df.dropna(subset=["price", "brand", "storage_gb"]).copy()

    categorical_cols = ["brand", "model", "condition_clean", "city", "seller_type"]
    numeric_cols = ["storage_gb", "photo_count"]

    X = model_df[categorical_cols + numeric_cols].copy()
    for col in categorical_cols:
        X[col] = X[col].astype("category")

    y = model_df["price"]
    y_log = np.log(y)

    def make_model():
        return xgb.XGBRegressor(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            enable_categorical=True,
            random_state=42,
        )

    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    oof_pred_log = np.zeros(len(model_df))
    for train_idx, val_idx in kf.split(X):
        fold_model = make_model()
        fold_model.fit(X.iloc[train_idx], y_log.iloc[train_idx])
        oof_pred_log[val_idx] = fold_model.predict(X.iloc[val_idx])

    oof_pred = np.exp(oof_pred_log)
    rmse = root_mean_squared_error(y, oof_pred)
    mape = mean_absolute_percentage_error(y, oof_pred) * 100

    last_mape = load_last_mape()
    degraded = last_mape is not None and mape > last_mape * DEGRADATION_THRESHOLD
    promoted = not degraded

    print(f"rows: {len(df)} | usable: {len(model_df)} | {N_SPLITS}-fold out-of-fold evaluation")
    print(f"RMSE: BDT {rmse:,.0f} | MAPE: {mape:.1f}% | last recorded MAPE: {last_mape}")

    if degraded:
        print(
            f"WARNING: MAPE {mape:.1f}% is more than {DEGRADATION_THRESHOLD}x the last "
            f"recorded {last_mape:.1f}% -- NOT promoting this model. Investigate before "
            f"the next run overwrites this warning."
        )
    else:
        model_df["predicted_price"] = oof_pred
        model_df["fair_price_min"] = (model_df["predicted_price"] * 0.9).round(0)
        model_df["fair_price_max"] = (model_df["predicted_price"] * 1.1).round(0)
        raw_score = 100 - (
            (model_df["price"] - model_df["predicted_price"]) / model_df["predicted_price"] * 100
        )
        model_df["deal_score"] = raw_score.clip(lower=0, upper=100).round(0)

        final_model = make_model()
        final_model.fit(X, y_log)
        final_model.save_model(MODEL_PATH)
        model_df.to_csv(RESULTS_PATH, index=False)
        write_predictions(conn, model_df)
        print(f"saved: {MODEL_PATH}, {RESULTS_PATH}, and wrote predictions to phones_normalized")

    conn.close()

    append_history(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_rows": len(df),
            "usable_rows": len(model_df),
            "rmse": round(rmse, 2),
            "mape_pct": round(mape, 2),
            "promoted": promoted,
        }
    )


if __name__ == "__main__":
    main()
