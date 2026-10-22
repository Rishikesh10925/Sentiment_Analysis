import pandas as pd

from ml.train import MODEL_PATH, METRICS_REPORT_PATH, VECTORIZER_PATH, run_training
from ml.predict import predict_dataframe, load_artifacts, run_predict


def test_run_training_produces_valid_metrics_and_saves_artifacts():
    report = run_training(save=True)

    assert report["training_rows"] > 0
    assert report["test_rows"] > 0
    assert report["selected_model"] in report["models"]

    for name, metrics in report["models"].items():
        for key in ("accuracy", "precision", "recall", "f1"):
            assert 0.0 <= metrics[key] <= 1.0
        cm = metrics["confusion_matrix"]
        assert len(cm) == 3 and all(len(row) == 3 for row in cm)
        assert sum(sum(row) for row in cm) == report["test_rows"]

    assert MODEL_PATH.exists()
    assert VECTORIZER_PATH.exists()
    assert METRICS_REPORT_PATH.exists()


def test_predict_dataframe_adds_prediction_columns():
    model, vectorizer = load_artifacts()
    df = pd.DataFrame({
        "clean_text": ["amazing product love it", "terrible service worst ever", "just an update today"],
    })
    result = predict_dataframe(df, model, vectorizer, text_column="clean_text")

    assert "predicted_sentiment" in result.columns
    assert set(result["predicted_sentiment"]).issubset({"Positive", "Neutral", "Negative"})
    assert "prediction_confidence" in result.columns
    assert result["prediction_confidence"].between(0, 1).all()


def test_run_predict_on_labeled_data_reports_evaluation(capsys):
    from ingestion.config import PROJECT_ROOT

    labeled_path = PROJECT_ROOT / "data" / "sample" / "social_media_sample_labeled.csv"
    result = run_predict(labeled_path, output_path=None, text_column="text", label_column="sentiment")

    captured = capsys.readouterr()
    assert "Evaluation against 'sentiment'" in captured.out
    assert "predicted_sentiment" in result.columns
