"""Load the saved CNN or KNN model and predict one hand sign."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

BASE_DIR = Path(__file__).resolve().parent
CNN_RUNTIME_PATH = BASE_DIR / "Models" / "CNN_Model_File" / "CNN_Runtime_Weights.npz"
CNN_METADATA_PATH = BASE_DIR / "Models" / "CNN_Model_File" / "cnn_metadata.json"
KNN_MODEL_PATH = BASE_DIR / "Models" / "KNN_Model_File" / "knn_model.npz"

DEFAULT_CLASSES = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "del", "nothing", "space",
]


@dataclass(frozen=True)
class Prediction:
    """A predicted sign and its confidence score."""

    label: str
    confidence: float


class BasePredictor:
    """Common prediction interface used by both models."""

    name = "Unknown"

    def predict(self, landmarks: np.ndarray) -> Prediction:
        """Predict one sign from 63 hand-landmark values."""
        raise NotImplementedError


class CNNPredictor(BasePredictor):
    """Run the trained CNN from exported NumPy weights."""

    name = "CNN"

    def __init__(self) -> None:
        """Load the CNN weights, class names, and normalisation value."""
        if not CNN_RUNTIME_PATH.exists():
            raise FileNotFoundError(
                f"CNN runtime weights are missing: {CNN_RUNTIME_PATH}\n"
                "Run training/train_cnn.py to create them again."
            )

        with np.load(CNN_RUNTIME_PATH, allow_pickle=False) as data:
            self.weights = {
                key: np.asarray(data[key], dtype=np.float32)
                for key in data.files
                if key != "batch_norm_epsilon"
            }
            self.batch_norm_epsilon = float(data["batch_norm_epsilon"])

        self.classes: Sequence[str] = DEFAULT_CLASSES
        self.norm_factor = 1.0
        if CNN_METADATA_PATH.exists():
            metadata = json.loads(CNN_METADATA_PATH.read_text(encoding="utf-8"))
            self.classes = [str(value) for value in metadata.get("classes", DEFAULT_CLASSES)]
            self.norm_factor = float(metadata.get("normalization_factor", 1.0))
        elif KNN_MODEL_PATH.exists():
            with np.load(KNN_MODEL_PATH, allow_pickle=True) as data:
                self.norm_factor = float(data["norm_factor"]) if "norm_factor" in data.files else 1.0

    @staticmethod
    def conv1d_same(x: np.ndarray, kernel: np.ndarray, bias: np.ndarray) -> np.ndarray:
        """Apply the same 1D cross-correlation used during training."""
        padding = (kernel.shape[0] - 1) // 2
        padded = np.pad(x, ((0, 0), (padding, padding), (0, 0)), mode="constant")
        windows = np.lib.stride_tricks.sliding_window_view(
            padded,
            window_shape=kernel.shape[0],
            axis=1,
        )
        return np.einsum("blck,kco->blo", windows, kernel, optimize=True) + bias

    def batch_norm(self, x: np.ndarray, prefix: str) -> np.ndarray:
        """Apply one saved batch-normalisation layer."""
        gamma = self.weights[f"{prefix}_gamma"]
        beta = self.weights[f"{prefix}_beta"]
        mean = self.weights[f"{prefix}_mean"]
        variance = self.weights[f"{prefix}_variance"]
        return gamma * (x - mean) / np.sqrt(variance + self.batch_norm_epsilon) + beta

    def forward(self, sample: np.ndarray) -> np.ndarray:
        """Run one hand sample through the CNN layers."""
        weights = self.weights
        x = sample.reshape(1, 21, 3)

        x = np.maximum(self.conv1d_same(x, weights["conv1_kernel"], weights["conv1_bias"]), 0.0)
        x = self.batch_norm(x, "bn1")
        x = np.maximum(self.conv1d_same(x, weights["conv2_kernel"], weights["conv2_bias"]), 0.0)
        x = self.batch_norm(x, "bn2")
        x = np.maximum(self.conv1d_same(x, weights["conv3_kernel"], weights["conv3_bias"]), 0.0)
        x = self.batch_norm(x, "bn3")

        x = x.reshape(1, -1)
        x = np.maximum(x @ weights["dense1_kernel"] + weights["dense1_bias"], 0.0)
        logits = x @ weights["output_kernel"] + weights["output_bias"]
        logits -= np.max(logits, axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= np.sum(probabilities, axis=1, keepdims=True)
        return probabilities[0]

    def predict(self, landmarks: np.ndarray) -> Prediction:
        """Normalise one sample and return the CNN prediction."""
        sample = np.asarray(landmarks, dtype=np.float32).reshape(63)
        if self.norm_factor > 0:
            sample = sample / self.norm_factor

        probabilities = self.forward(sample)
        index = int(np.argmax(probabilities))
        return Prediction(str(self.classes[index]), float(probabilities[index]))


class KNNPredictor(BasePredictor):
    """Predict a sign from nearby saved landmark samples."""

    name = "KNN"

    def __init__(self) -> None:
        """Load the saved KNN samples and settings."""
        if not KNN_MODEL_PATH.exists():
            raise FileNotFoundError(f"KNN model is missing: {KNN_MODEL_PATH}")

        with np.load(KNN_MODEL_PATH, allow_pickle=True) as data:
            self.x_train = np.asarray(data["X_train"], dtype=np.float32)
            self.y_train = np.asarray(data["y_train"], dtype=np.int32)
            self.k = int(data["k"])
            self.classes = [str(value) for value in data["classes"]]
            self.norm_factor = float(data["norm_factor"])

    def predict(self, landmarks: np.ndarray) -> Prediction:
        """Find the nearest saved samples and return the majority label."""
        sample = np.asarray(landmarks, dtype=np.float32).reshape(63)
        if self.norm_factor > 0:
            sample = sample / self.norm_factor

        distances = np.linalg.norm(self.x_train - sample, axis=1)
        nearest = np.argpartition(distances, self.k - 1)[: self.k]
        labels = self.y_train[nearest]
        counts = np.bincount(labels, minlength=len(self.classes))
        index = int(np.argmax(counts))
        confidence = float(counts[index] / self.k)
        return Prediction(self.classes[index], confidence)


def create_predictor(model_name: str) -> BasePredictor:
    """Create the predictor selected in the main window."""
    normalized = model_name.strip().lower()
    if normalized == "cnn":
        return CNNPredictor()
    if normalized == "knn":
        return KNNPredictor()
    raise ValueError("Choose either 'cnn' or 'knn'.")
