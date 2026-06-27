import argparse
import os
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from utils import clean_text, detect_threats


DEFAULT_TEXT_COLUMNS = (
    "text",
    "comment",
    "content",
    "message",
    "tweet",
    "tweet_text",
    "sentence",
)

DEFAULT_LABEL_COLUMNS = (
    "label",
    "category",
    "class",
    "target",
    "type",
    "cyberbullying_type",
    "bullying_type",
)

DEFAULT_SENTIMENT_COLUMNS = (
    "sentiment",
    "sentiment_label",
    "polarity",
    "avg_sentiment",
)

NORMAL_LABELS = {
    "normal",
    "not cyberbullying",
    "not_cyberbullying",
    "non cyberbullying",
    "non-cyberbullying",
    "non bullying",
    "non-bullying",
    "clean",
    "safe",
    "none",
    "neutral",
}


def find_column(columns: Iterable[str], preferred_names: Iterable[str]) -> str | None:
    normalized = {column.lower().strip(): column for column in columns}
    for name in preferred_names:
        if name in normalized:
            return normalized[name]
    return None


def normalize_label(value) -> str:
    label = str(value).strip()
    if not label or label.lower() == "nan":
        return ""

    cleaned = label.replace("_", " ").replace("-", " ")
    cleaned = " ".join(cleaned.split())
    lower = cleaned.lower()

    if lower in NORMAL_LABELS:
        return "Normal"

    aliases = {
        "cyberbullying": "Harassment",
        "bullying": "Harassment",
        "offensive": "Harassment",
        "harassment": "Harassment",
        "hate": "Hate Speech",
        "hate speech": "Hate Speech",
        "hatespeech": "Hate Speech",
        "religion": "Religious Abuse",
        "religious": "Religious Abuse",
        "religious abuse": "Religious Abuse",
        "gender": "Gender Abuse",
        "gender abuse": "Gender Abuse",
        "sexism": "Gender Abuse",
        "threat": "Threat",
        "threats": "Threat",
    }
    if lower in aliases:
        return aliases[lower]

    return cleaned.title()


def normalize_sentiment(value) -> str:
    try:
        numeric = float(value)
        if numeric > 0.15:
            return "Positive"
        if numeric < -0.15:
            return "Negative"
        return "Neutral"
    except (TypeError, ValueError):
        pass

    sentiment = str(value).strip().lower()
    if sentiment in {"positive", "pos", "1"}:
        return "Positive"
    if sentiment in {"negative", "neg", "-1"}:
        return "Negative"
    return "Neutral"


def load_dataset(path: str, text_column: str | None, label_column: str | None, sentiment_column: str | None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif ext == ".json":
        df = pd.read_json(path)
    else:
        raise ValueError("Unsupported dataset format. Use CSV, XLSX, XLS, or JSON.")

    if df.empty:
        raise ValueError("Dataset is empty.")

    text_column = text_column or find_column(df.columns, DEFAULT_TEXT_COLUMNS)
    label_column = label_column or find_column(df.columns, DEFAULT_LABEL_COLUMNS)
    sentiment_column = sentiment_column or find_column(df.columns, DEFAULT_SENTIMENT_COLUMNS)

    if not text_column or text_column not in df.columns:
        raise ValueError(
            "Text column was not found. Pass it explicitly, for example: "
            "--text-column comment_text"
        )
    if not label_column or label_column not in df.columns:
        raise ValueError(
            "Label column was not found. Pass it explicitly, for example: "
            "--label-column cyberbullying_type"
        )

    prepared = pd.DataFrame()
    prepared["text"] = df[text_column].fillna("").astype(str)
    prepared["original_text"] = prepared["text"].copy()  # Save original for threat detection
    
    # Custom demographic-aware mapping if demographics exist in the dataset (e.g., HateXplain)
    if "Religion" in df.columns and "Gender" in df.columns:
        labels = []
        for idx, row in df.iterrows():
            orig_text = str(row[text_column]).strip()
            orig_lbl = str(row[label_column]).strip().lower()
            
            # Noise reduction: normal/clean comments are NEVER mapped to Threat.
            # Only abusive comments containing threat keywords are mapped to Threat.
            is_threat = detect_threats(orig_text)
            
            if orig_lbl in NORMAL_LABELS:
                labels.append("Normal")
            elif is_threat:
                labels.append("Threat")
            elif orig_lbl in ("hatespeech", "hate speech", "offensive"):
                religion = str(row.get("Religion", "Nonreligious")).strip()
                gender = str(row.get("Gender", "No_gender")).strip()
                orientation = str(row.get("Sexual Orientation", "No_orientation")).strip()
                
                if religion != "Nonreligious":
                    labels.append("Religious Abuse")
                elif gender != "No_gender" or orientation != "No_orientation":
                    labels.append("Gender Abuse")
                elif orig_lbl == "offensive":
                    labels.append("Harassment")
                else:
                    labels.append("Hate Speech")
            else:
                labels.append(normalize_label(row[label_column]))
        prepared["label"] = labels
    else:
        # For datasets without demographics, use threat detection + standard mapping
        labels = []
        for idx, row in df.iterrows():
            orig_text = str(row[text_column]).strip()
            orig_lbl = str(row[label_column]).strip().lower()
            is_threat = detect_threats(orig_text)
            
            if orig_lbl in NORMAL_LABELS:
                labels.append("Normal")
            elif is_threat:
                labels.append("Threat")
            else:
                labels.append(normalize_label(row[label_column]))
        prepared["label"] = labels

    if sentiment_column and sentiment_column in df.columns:
        prepared["sentiment"] = df[sentiment_column].apply(normalize_sentiment)
    else:
        prepared["sentiment"] = prepared["label"].apply(
            lambda label: "Neutral" if label == "Normal" else "Negative"
        )

    original_rows = len(prepared)
    prepared["cleaned_text"] = prepared["text"].apply(clean_text)
    prepared = prepared[(prepared["cleaned_text"] != "") & (prepared["label"] != "")]
    rows_after_cleaning = len(prepared)
    prepared = prepared.drop_duplicates(subset=["cleaned_text", "label"])
    duplicate_rows_removed = rows_after_cleaning - len(prepared)

    if prepared.empty:
        raise ValueError("No usable rows left after preprocessing.")

    dataset_report = {
        "original_rows": original_rows,
        "rows_after_cleaning": rows_after_cleaning,
        "duplicate_rows_removed": duplicate_rows_removed,
    }

    return prepared, text_column, label_column, sentiment_column, dataset_report


def build_text_classifier(cv_folds: int) -> Pipeline:
    if cv_folds >= 2:
        classifier = CalibratedClassifierCV(
            estimator=LinearSVC(class_weight="balanced", C=0.5, max_iter=5000),
            cv=cv_folds,
        )
    else:
        classifier = LogisticRegression(
            class_weight="balanced",
            C=5.0,
            max_iter=2000,
        )

    return Pipeline(
        [
            (
                "features",
                FeatureUnion(
                    [
                        (
                            "word_tfidf",
                            TfidfVectorizer(
                                analyzer="word",
                                ngram_range=(1, 2),
                                min_df=2,
                                sublinear_tf=True,
                                max_features=60000,
                            ),
                        ),
                        (
                            "char_tfidf",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                min_df=3,
                                sublinear_tf=True,
                                max_features=50000,
                            ),
                        ),
                    ]
                ),
            ),
            ("clf", classifier),
        ]
    )


def safe_stratify(labels: pd.Series):
    counts = labels.value_counts()
    if len(counts) < 2 or counts.min() < 2:
        return None
    return labels


def train_classifier(df: pd.DataFrame, target_column: str, model_name: str):
    label_counts = df[target_column].value_counts()
    rare_labels = label_counts[label_counts < 2].index
    if len(rare_labels):
        df = df[~df[target_column].isin(rare_labels)].copy()

    if df[target_column].nunique() < 2:
        raise ValueError(f"{model_name} training needs at least two classes.")

    x_train, x_test, y_train, y_test = train_test_split(
        df["cleaned_text"],
        df[target_column],
        test_size=0.2,
        random_state=42,
        stratify=safe_stratify(df[target_column]),
    )

    min_training_class_count = y_train.value_counts().min()
    cv_folds = min(3, int(min_training_class_count))
    pipeline = build_text_classifier(cv_folds)
    pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_test)
    print(f"\n{model_name} evaluation")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    pipeline.fit(df["cleaned_text"], df[target_column])
    return pipeline, df


def encode_labels(labels: pd.Series):
    classes = sorted(labels.unique().tolist())
    class_to_index = {label: index for index, label in enumerate(classes)}
    encoded = labels.map(class_to_index).astype(int)
    return encoded, classes


def build_lstm_model(vectorizer, class_count: int, embedding_dim: int, lstm_units: int, dropout: float):
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow is required for LSTM training. "
            "Install dependencies first: pip install -r requirements.txt"
        ) from exc

    model = tf.keras.Sequential(
        [
            tf.keras.Input(shape=(1,), dtype=tf.string),
            vectorizer,
            tf.keras.layers.Embedding(
                input_dim=vectorizer.vocabulary_size(),
                output_dim=embedding_dim,
                mask_zero=True,
            ),
            tf.keras.layers.SpatialDropout1D(0.3),
            tf.keras.layers.Bidirectional(
                tf.keras.layers.LSTM(lstm_units, return_sequences=False, dropout=0.2, recurrent_dropout=0.2)
            ),
            tf.keras.layers.Dropout(dropout),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dropout(dropout),
            tf.keras.layers.Dense(class_count, activation="softmax"),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def build_lstm_callbacks(patience: int):
    import tensorflow as tf

    return [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
        )
    ]


def train_lstm_classifier(df: pd.DataFrame, target_column: str, model_name: str, args):
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow is required for LSTM training. "
            "Install dependencies first: pip install -r requirements.txt"
        ) from exc

    label_counts = df[target_column].value_counts()
    rare_labels = label_counts[label_counts < 2].index
    if len(rare_labels):
        df = df[~df[target_column].isin(rare_labels)].copy()

    if df[target_column].nunique() < 2:
        raise ValueError(f"{model_name} training needs at least two classes.")

    encoded_labels, classes = encode_labels(df[target_column])
    x_train, x_test, y_train, y_test = train_test_split(
        df["cleaned_text"],
        encoded_labels,
        test_size=0.2,
        random_state=42,
        stratify=safe_stratify(df[target_column]),
    )

    from sklearn.utils.class_weight import compute_class_weight
    unique_train_classes = np.unique(y_train)
    train_class_weights = compute_class_weight(
        class_weight="balanced",
        classes=unique_train_classes,
        y=np.array(y_train)
    )
    train_class_weight_dict = dict(zip(unique_train_classes, train_class_weights))

    vectorizer = tf.keras.layers.TextVectorization(
        max_tokens=args.max_tokens,
        output_mode="int",
        output_sequence_length=args.sequence_length,
        standardize=None,
    )
    vectorizer.adapt(np.array(x_train, dtype=object))

    model = build_lstm_model(
        vectorizer=vectorizer,
        class_count=len(classes),
        embedding_dim=args.embedding_dim,
        lstm_units=args.lstm_units,
        dropout=args.dropout,
    )

    model.fit(
        np.array(x_train, dtype=object),
        np.array(y_train),
        validation_split=0.2,
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=build_lstm_callbacks(args.patience),
        class_weight=train_class_weight_dict,
        verbose=1,
    )

    probabilities = model.predict(np.array(x_test, dtype=object), verbose=0)
    y_pred = np.argmax(probabilities, axis=1)
    print(f"\n{model_name} LSTM evaluation")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(classification_report(y_test, y_pred, target_names=classes, zero_division=0))

    # Refit vectorizer and model on all available examples for the saved artifact.
    vectorizer = tf.keras.layers.TextVectorization(
        max_tokens=args.max_tokens,
        output_mode="int",
        output_sequence_length=args.sequence_length,
        standardize=None,
    )
    vectorizer.adapt(np.array(df["cleaned_text"], dtype=object))
    model = build_lstm_model(
        vectorizer=vectorizer,
        class_count=len(classes),
        embedding_dim=args.embedding_dim,
        lstm_units=args.lstm_units,
        dropout=args.dropout,
    )

    unique_full_classes = np.unique(encoded_labels)
    full_class_weights = compute_class_weight(
        class_weight="balanced",
        classes=unique_full_classes,
        y=np.array(encoded_labels)
    )
    full_class_weight_dict = dict(zip(unique_full_classes, full_class_weights))

    model.fit(
        np.array(df["cleaned_text"], dtype=object),
        np.array(encoded_labels),
        validation_split=0.1,
        epochs=args.epochs,
        batch_size=args.batch_size,
        callbacks=build_lstm_callbacks(args.patience),
        class_weight=full_class_weight_dict,
        verbose=1,
    )

    return model, classes, df


def load_training_data(args):
    dataset_path = os.path.abspath(args.dataset)
    df, text_column, label_column, sentiment_column, dataset_report = load_dataset(
        dataset_path,
        args.text_column,
        args.label_column,
        args.sentiment_column,
    )

    print("Dataset loaded successfully")
    print(f"Path: {dataset_path}")
    print(f"Original rows: {dataset_report['original_rows']}")
    print(f"Rows after cleaning: {dataset_report['rows_after_cleaning']}")
    print(f"Duplicate text rows removed: {dataset_report['duplicate_rows_removed']}")
    print(f"Rows after preprocessing: {len(df)}")
    print(f"Text column: {text_column}")
    print(f"Label column: {label_column}")
    print(f"Sentiment column: {sentiment_column or 'not provided; derived from labels'}")
    print("\nCyberbullying labels:")
    print(df["label"].value_counts().to_string())
    return df, dataset_path, text_column, label_column, sentiment_column, dataset_report


def train_sklearn_models(args):
    df, dataset_path, text_column, label_column, sentiment_column, _ = load_training_data(args)

    cb_pipeline, cb_df = train_classifier(df, "label", "Cyberbullying classifier")
    sent_pipeline, sent_df = train_classifier(df, "sentiment", "Sentiment classifier")

    model_path = os.path.abspath(args.output)
    model_data = {
        "cyberbullying_pipeline": cb_pipeline,
        "sentiment_pipeline": sent_pipeline,
        "cyberbullying_classes": cb_pipeline.named_steps["clf"].classes_.tolist(),
        "sentiment_classes": sent_pipeline.named_steps["clf"].classes_.tolist(),
        "metadata": {
            "dataset_path": dataset_path,
            "rows_used_for_cyberbullying": len(cb_df),
            "rows_used_for_sentiment": len(sent_df),
            "text_column": text_column,
            "label_column": label_column,
            "sentiment_column": sentiment_column,
            "preprocessing": "backend.utils.clean_text",
            "model": "Calibrated LinearSVC with word and character TF-IDF features",
        },
    }

    joblib.dump(model_data, model_path)
    print(f"\nModel saved to {model_path}")


def train_lstm_models(args):
    df, dataset_path, text_column, label_column, sentiment_column, _ = load_training_data(args)

    cb_model, cb_classes, cb_df = train_lstm_classifier(
        df,
        "label",
        "Cyberbullying classifier",
        args,
    )
    sent_model, sent_classes, sent_df = train_lstm_classifier(
        df,
        "sentiment",
        "Sentiment classifier",
        args,
    )

    model_path = os.path.abspath(args.output)
    model_dir = os.path.dirname(model_path)
    cb_model_name = "cyberbullying_lstm.keras"
    sent_model_name = "sentiment_lstm.keras"

    cb_model.save(os.path.join(model_dir, cb_model_name))
    sent_model.save(os.path.join(model_dir, sent_model_name))

    model_data = {
        "model_type": "lstm",
        "cyberbullying_model_path": cb_model_name,
        "sentiment_model_path": sent_model_name,
        "cyberbullying_classes": cb_classes,
        "sentiment_classes": sent_classes,
        "metadata": {
            "dataset_path": dataset_path,
            "rows_used_for_cyberbullying": len(cb_df),
            "rows_used_for_sentiment": len(sent_df),
            "text_column": text_column,
            "label_column": label_column,
            "sentiment_column": sentiment_column,
            "preprocessing": "backend.utils.clean_text",
            "model": "Keras TextVectorization + Embedding + Bidirectional LSTM",
            "max_tokens": args.max_tokens,
            "sequence_length": args.sequence_length,
            "embedding_dim": args.embedding_dim,
            "lstm_units": args.lstm_units,
        },
    }

    joblib.dump(model_data, model_path)
    print(f"\nLSTM model metadata saved to {model_path}")
    print(f"Cyberbullying LSTM saved to {os.path.join(model_dir, cb_model_name)}")
    print(f"Sentiment LSTM saved to {os.path.join(model_dir, sent_model_name)}")


def train_models(args):
    if args.model == "sklearn":
        train_sklearn_models(args)
    else:
        train_lstm_models(args)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train cyberbullying detection models from an external dataset."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to your CSV, XLSX, XLS, or JSON dataset.",
    )
    parser.add_argument(
        "--text-column",
        default=None,
        help="Name of the column containing comment/message text. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--label-column",
        default=None,
        help="Name of the cyberbullying label/category column. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--sentiment-column",
        default=None,
        help="Optional sentiment column. If omitted, Normal becomes Neutral and toxic labels become Negative.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(os.path.dirname(__file__), "model.joblib"),
        help="Output path for the trained model artifact.",
    )
    parser.add_argument(
        "--model",
        choices=["lstm", "sklearn"],
        default="lstm",
        help="Model family to train. Default is lstm.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=15000,
        help="Maximum vocabulary size for the LSTM text vectorizer.",
    )
    parser.add_argument(
        "--sequence-length",
        type=int,
        default=80,
        help="Fixed token sequence length for LSTM inputs.",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=64,
        help="Embedding vector size for the LSTM model.",
    )
    parser.add_argument(
        "--lstm-units",
        type=int,
        default=64,
        help="Number of LSTM units in each direction.",
    )
    parser.add_argument(
        "--dropout",
        type=float,
        default=0.35,
        help="Dropout rate used in the LSTM classifier.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=12,
        help="Maximum number of LSTM training epochs.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="LSTM training batch size.",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=3,
        help="Early-stopping patience for LSTM validation loss.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    train_models(parse_args())
