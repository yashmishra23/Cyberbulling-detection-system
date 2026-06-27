import builtins
import contextlib
import os

import joblib
import numpy as np


@contextlib.contextmanager
def _utf8_open():
    """Temporarily force UTF-8 encoding for all text-mode file operations.

    On Windows the default encoding is CP1252 which cannot handle emoji
    characters stored inside Keras TextVectorization vocabularies.
    This context manager monkey-patches ``builtins.open`` so that
    ``tf.keras.models.load_model`` reads those files as UTF-8.
    """
    _original = builtins.open

    def _patched(*args, **kwargs):
        # Only inject encoding for text-mode opens that don't already specify one.
        mode = args[1] if len(args) >= 2 else kwargs.get("mode", "r")
        if "b" not in mode and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        return _original(*args, **kwargs)

    builtins.open = _patched
    try:
        yield
    finally:
        builtins.open = _original


class KerasTextClassifier:
    def __init__(self, model_path: str, classes: list[str]):
        try:
            import tensorflow as tf
        except ImportError as exc:
            raise RuntimeError(
                "TensorFlow is required to load the LSTM model. "
                "Install backend requirements first: pip install -r requirements.txt"
            ) from exc

        with _utf8_open():
            self.model = tf.keras.models.load_model(model_path)
        self.classes_ = np.array(classes)

    def predict_proba(self, texts):
        probs = self.model.predict(np.array(list(texts), dtype=object), verbose=0)
        return np.asarray(probs, dtype=float)

    def predict(self, texts):
        probs = self.predict_proba(texts)
        indexes = np.argmax(probs, axis=1)
        return self.classes_[indexes]


def load_model_bundle(model_path: str):
    artifact = joblib.load(model_path)
    model_type = artifact.get("model_type", "sklearn")

    if model_type != "lstm":
        return {
            "model_type": "sklearn",
            "cyberbullying_pipeline": artifact["cyberbullying_pipeline"],
            "sentiment_pipeline": artifact["sentiment_pipeline"],
        }

    # Only import TensorFlow if we actually need LSTM models
    try:
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError(
            "TensorFlow is required to load the LSTM model. "
            "Install backend requirements first: pip install -r requirements.txt"
        ) from exc

    base_dir = os.path.dirname(model_path)
    cb_model_path = os.path.join(base_dir, artifact["cyberbullying_model_path"])
    sent_model_path = os.path.join(base_dir, artifact["sentiment_model_path"])

    return {
        "model_type": "lstm",
        "cyberbullying_pipeline": KerasTextClassifier(
            cb_model_path,
            artifact["cyberbullying_classes"],
        ),
        "sentiment_pipeline": KerasTextClassifier(
            sent_model_path,
            artifact["sentiment_classes"],
        ),
    }


def predict_with_confidence(model, cleaned_text: str):
    prediction = str(model.predict([cleaned_text])[0])
    probabilities = model.predict_proba([cleaned_text])[0]

    classes = getattr(model, "classes_", None)
    if classes is None and hasattr(model, "named_steps"):
        classes = model.named_steps["clf"].classes_

    if classes is None:
        confidence = float(np.max(probabilities))
    else:
        classes = np.asarray(classes)
        index = np.where(classes == prediction)[0][0]
        confidence = float(probabilities[index])

    return prediction, confidence
