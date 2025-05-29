from flask import Blueprint, request, jsonify
import pandas as pd
import os

length_bp = Blueprint("length", __name__, url_prefix="/api/lengths")

# Define relative paths to CSVs
base_dir = os.path.dirname(__file__)
csv_paths = {
    "length": os.path.join(base_dir, "../length.csv"),
    "audience": os.path.join(base_dir, "../audience.csv"),
    "performance": os.path.join(base_dir, "../performance.csv"),
    "sentiment": os.path.join(base_dir, "../sentiment.csv"),
    "metadata": os.path.join(base_dir, "../metadata.csv"),
}

# Load and cache merged data once on startup
def load_and_merge_data():
    dfs = {k: pd.read_csv(p) for k, p in csv_paths.items()}
    merged = dfs["length"]
    for key, df in dfs.items():
        if key != "length":
            merged = pd.merge(merged, df, on="video_length_seconds", how="left")
    # Convert contains_hook to boolean for convenience
    merged["contains_hook"] = merged["contains_hook"].astype(str).str.strip().str.lower() == "yes"
    return merged

merged_df = load_and_merge_data()

@length_bp.route("/predict", methods=["GET"])
def predict():
    try:
        video_length = int(request.args.get("video_length_seconds"))
        # Find closest match by video length
        closest_row = merged_df.iloc[(merged_df["video_length_seconds"] - video_length).abs().argmin()]

        result = {
            "input_length": video_length,
            "closest_match": int(closest_row["video_length_seconds"]),
            "engagement_quality": str(closest_row["engagement_quality"]),
            "views": int(closest_row["views"]),
            "likes": int(closest_row["likes"]),
            "comments": int(closest_row["comments"]),
            "watch_time_seconds": int(closest_row["watch_time_seconds"]),
            "avg_retention_percent": float(closest_row["avg_retention_percent"]),
            "drop_off_rate": float(closest_row["drop_off_rate"]),
            "click_through_rate_percent": float(closest_row["click_through_rate_percent"]),
            "avg_weekly_views_increase": float(closest_row["avg_weekly_views_increase"]),
            "share_rate_percent": float(closest_row["share_rate_percent"]),
            "sentiment": {
                "positive": int(closest_row["positive"]),
                "neutral": int(closest_row["neutral"]),
                "negative": int(closest_row["negative"]),
                "total_comments": int(closest_row["total_comments"])
            },
            "tags": str(closest_row["top_tags"]),
            "category": str(closest_row["category"]),
            "thumbnail_click_rate_percent": float(closest_row["avg_thumbnail_click_rate_percent"]),
            "contains_hook": bool(closest_row["contains_hook"])
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@length_bp.route("/", methods=["GET"])
def get_all():
    try:
        records = merged_df.where(pd.notnull(merged_df), None).to_dict(orient="records")
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@length_bp.route("/summary", methods=["GET"])
def summary():
    try:
        # Basic stats about video length
        min_length = int(merged_df["video_length_seconds"].min())
        max_length = int(merged_df["video_length_seconds"].max())
        avg_length = float(merged_df["video_length_seconds"].mean())

        # Top 5 video lengths by engagement_quality (assuming engagement_quality can be ranked)
        # If engagement_quality is categorical (e.g., "High", "Medium", "Low"), you can map to numeric for sorting
        engagement_map = {"Low": 1, "Medium": 2, "High": 3}
        merged_df["engagement_rank"] = merged_df["engagement_quality"].map(engagement_map).fillna(0)
        top_engagement = merged_df.sort_values(by="engagement_rank", ascending=False).head(5)
        top_engagement_list = top_engagement[["video_length_seconds", "engagement_quality"]].to_dict(orient="records")

        return jsonify({
            "min_length": min_length,
            "max_length": max_length,
            "avg_length": avg_length,
            "top_engagement": top_engagement_list
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@length_bp.route("/chart-data", methods=["GET"])
def chart_data():
    try:
        # Return trimmed data for charts
        # Let's provide video_length_seconds and key metrics for charts
        data = merged_df[[
            "video_length_seconds",
            "engagement_quality",
            "views",
            "likes",
            "comments",
            "avg_retention_percent",
            "drop_off_rate",
            "click_through_rate_percent",
            "share_rate_percent",
            "positive",
            "neutral",
            "negative"
        ]]

        # Map engagement_quality to numeric score for charting
        engagement_map = {"Low": 1, "Medium": 2, "High": 3}
        data["engagement_rank"] = data["engagement_quality"].map(engagement_map).fillna(0)

        records = data.where(pd.notnull(data), None).to_dict(orient="records")
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500