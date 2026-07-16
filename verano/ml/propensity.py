"""Module 4 — Purchase propensity.

A simple, interpretable model: logistic regression on RFM + engagement features.
Uses a TEMPORAL split to avoid leakage — features are built as of a cutoff, the
label is "did the customer purchase in the following window":

    features: all behaviour before 2026-03-01  (Nov–Feb)
    label:    purchased in 2026-03-01 .. window end  (Mar–Apr)

Because the positive rate is low (~5–8%), the model is class-balanced and we report
PR-AUC alongside ROC-AUC. Scores are then produced for all customers using features
as of the END of the window (current propensity).

    task verano:ml:propensity
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import mlbase as M
from features import FEATURE_COLS, build_features

CUTOFF = pd.Timestamp("2026-03-01")


def build() -> None:
    con = M.connect()

    # Training frame: features as of CUTOFF, label = purchased in [CUTOFF, end].
    feat = build_features(con, CUTOFF)
    buyers = con.execute("""
        select distinct customer_id
        from gold.fact_order
        where customer_id is not null and order_status <> 'cancelled'
          and order_at >= $cutoff
    """, {"cutoff": CUTOFF}).df()["customer_id"]
    feat["label"] = feat["customer_id"].isin(set(buyers)).astype(int)

    pos_rate = feat["label"].mean()
    print(f"Training: {len(feat):,} customers, {feat['label'].sum():,} positives "
          f"({pos_rate:.1%} base rate)")

    X, y = feat[FEATURE_COLS].to_numpy(float), feat["label"].to_numpy()
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=M.SEED, stratify=y)

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000, random_state=M.SEED),
    )
    model.fit(X_tr, y_tr)
    proba_te = model.predict_proba(X_te)[:, 1]

    roc = roc_auc_score(y_te, proba_te)
    pr = average_precision_score(y_te, proba_te)
    print(f"\nHold-out metrics:")
    print(f"  ROC-AUC : {roc:.3f}")
    print(f"  PR-AUC  : {pr:.3f}   (baseline = base rate {y_te.mean():.3f})")

    # Coefficients (on standardised features) — the interpretability story.
    coefs = pd.DataFrame({
        "feature": FEATURE_COLS,
        "coefficient": model.named_steps["logisticregression"].coef_[0],
    }).sort_values("coefficient", key=abs, ascending=False)
    M.rule("Top drivers (standardised logistic coefficients)")
    print(coefs.head(8).to_string(index=False))

    # Decile lift on the hold-out.
    te = pd.DataFrame({"y": y_te, "p": proba_te})
    te["decile"] = pd.qcut(te["p"].rank(method="first"), 10, labels=False)
    lift = te.groupby("decile")["y"].mean().iloc[::-1]
    M.rule("Decile lift (hold-out) — purchase rate by predicted-propensity decile")
    print("  top decile purchase rate {:.1%}  vs  overall {:.1%}  ({:.1f}x lift)".format(
        lift.iloc[0], y_te.mean(), lift.iloc[0] / max(y_te.mean(), 1e-9)))

    # ── Production scores: features as of window end, score everyone ─────────
    feat_now = build_features(con, M.WINDOW_END)
    scores = model.predict_proba(feat_now[FEATURE_COLS].to_numpy(float))[:, 1]
    out = pd.DataFrame({
        "customer_id": feat_now["customer_id"],
        "purchase_propensity": scores,
        "has_prior_order": feat_now["has_prior_order"].astype(int),
    })
    out["propensity_decile"] = pd.qcut(out["purchase_propensity"].rank(method="first"),
                                       10, labels=False) + 1
    out = out.sort_values("purchase_propensity", ascending=False).reset_index(drop=True)
    M.write_ml_table(con, "propensity_scores", out)
    con.close()


if __name__ == "__main__":
    build()
