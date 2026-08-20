"""Train and evaluate the landmark KNN model."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA = PROJECT_DIR / "Processed_ASL_Dataset" / "Processed_ASL_Dataset_Train.npz"
DEFAULT_OUTPUT = PROJECT_DIR / "Models" / "KNN_Model_File"


class KNNClassifier:
    """A small KNN classifier used directly by the training script."""

    def __init__(self, k: int = 5) -> None:
        """Store the neighbour count and initialise the training data."""
        self.k = k
        self.x_train: np.ndarray | None = None
        self.y_train: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        """Store the training samples used by KNN."""
        self.x_train = x
        self.y_train = y

    def predict_one(self, sample: np.ndarray) -> int:
        """Return the majority label from the nearest samples."""
        if self.x_train is None or self.y_train is None:
            raise RuntimeError("Fit the classifier before asking it for a prediction.")
        distances = np.linalg.norm(self.x_train - sample, axis=1)
        nearest = np.argpartition(distances, self.k - 1)[: self.k]
        labels = self.y_train[nearest]
        return int(np.argmax(np.bincount(labels)))

    def predict(self, samples: np.ndarray) -> np.ndarray:
        """Predict all samples and return their labels."""
        return np.asarray([self.predict_one(sample) for sample in samples], dtype=np.int32)


def save_confusion_matrix(matrix: np.ndarray, classes: list[str], path: Path) -> None:
    """Save a labelled confusion matrix beside the KNN model."""
    figure = plt.figure(figsize=(12, 10))
    plt.imshow(matrix, cmap="Blues")
    plt.colorbar()
    ticks = np.arange(len(classes))
    plt.xticks(ticks, classes, rotation=90)
    plt.yticks(ticks, classes)
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title("KNN Confusion Matrix")
    plt.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def train(data_path: Path, output_dir: Path, k: int) -> None:
    """Split the data, evaluate KNN, and save the model and report."""
    if not data_path.exists():
        raise FileNotFoundError(f"Processed dataset was not found: {data_path}")

    with np.load(data_path, allow_pickle=True) as data:
        x = np.asarray(data["X"], dtype=np.float32)
        y = np.asarray(data["y"], dtype=np.int32)
        classes = [str(value) for value in data["classes"]]

    norm_factor = float(np.max(np.abs(x))) or 1.0
    x = x / norm_factor
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.30,
        stratify=y,
        random_state=42,
    )

    classifier = KNNClassifier(k)
    classifier.fit(x_train, y_train)
    predictions = classifier.predict(x_test)

    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        output_dir / "knn_model.npz",
        X_train=x_train,
        y_train=y_train,
        k=k,
        classes=np.asarray(classes),
        norm_factor=norm_factor,
    )

    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions, average="weighted", zero_division=0)
    recall = recall_score(y_test, predictions, average="weighted", zero_division=0)
    f1 = f1_score(y_test, predictions, average="weighted", zero_division=0)
    report = classification_report(y_test, predictions, target_names=classes, zero_division=0)
    (output_dir / "KNN_Evaluation_Metrics.txt").write_text(
        f"KNN Landmark Model\nK = {k}\nAccuracy: {accuracy:.4f}\n"
        f"Precision: {precision:.4f}\nRecall: {recall:.4f}\nF1 Score: {f1:.4f}\n\n"
        f"Classification Report:\n{report}",
        encoding="utf-8",
    )
    save_confusion_matrix(
        confusion_matrix(y_test, predictions),
        classes,
        output_dir / "KNN_Confusion_Matrix.png",
    )
    print(f"KNN model saved in: {output_dir}")


def parse_args() -> argparse.Namespace:
    """Read the data path, output folder, and K value."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    """Run KNN training with the chosen command-line settings."""
    args = parse_args()
    train(args.data.resolve(), args.output_dir.resolve(), args.k)


if __name__ == "__main__":
    main()
