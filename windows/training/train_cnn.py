"""Train the landmark CNN, evaluate it, and export its desktop weights."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
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
DEFAULT_OUTPUT = PROJECT_DIR / "Models" / "CNN_Model_File"


def load_data(path: Path) -> tuple[np.ndarray, np.ndarray, list[str], float]:
    """Load the landmark data and scale it with one saved factor."""
    with np.load(path, allow_pickle=True) as data:
        x = np.asarray(data["X"], dtype=np.float32)
        y = np.asarray(data["y"], dtype=np.int32)
        classes = [str(value) for value in data["classes"]]

    norm_factor = float(np.max(np.abs(x)))
    if norm_factor <= 0:
        norm_factor = 1.0
    return x / norm_factor, y, classes, norm_factor


def build_model(number_of_classes: int) -> tf.keras.Model:
    """Build the three-layer 1D CNN used for hand landmarks."""
    layers = tf.keras.layers
    model = tf.keras.Sequential(
        [
            layers.Input(shape=(63,)),
            layers.Reshape((21, 3)),
            layers.Conv1D(64, 3, activation="relu", padding="same", name="conv1d"),
            layers.BatchNormalization(name="batch_normalization"),
            layers.Conv1D(128, 3, activation="relu", padding="same", name="conv1d_1"),
            layers.BatchNormalization(name="batch_normalization_1"),
            layers.Conv1D(256, 3, activation="relu", padding="same", name="conv1d_2"),
            layers.BatchNormalization(name="batch_normalization_2"),
            layers.Flatten(),
            layers.Dense(256, activation="relu", name="dense"),
            layers.Dropout(0.4),
            layers.Dense(number_of_classes, activation="softmax", name="dense_1"),
        ]
    )
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def export_runtime_weights(model: tf.keras.Model, path: Path) -> None:
    """Export only the arrays needed by the desktop NumPy runtime."""
    arrays: dict[str, np.ndarray] = {}

    for number, layer_name in enumerate(("conv1d", "conv1d_1", "conv1d_2"), start=1):
        kernel, bias = model.get_layer(layer_name).get_weights()
        arrays[f"conv{number}_kernel"] = np.asarray(kernel, dtype=np.float32)
        arrays[f"conv{number}_bias"] = np.asarray(bias, dtype=np.float32)

    batch_layers = (
        "batch_normalization",
        "batch_normalization_1",
        "batch_normalization_2",
    )
    for number, layer_name in enumerate(batch_layers, start=1):
        gamma, beta, moving_mean, moving_variance = model.get_layer(layer_name).get_weights()
        arrays[f"bn{number}_gamma"] = np.asarray(gamma, dtype=np.float32)
        arrays[f"bn{number}_beta"] = np.asarray(beta, dtype=np.float32)
        arrays[f"bn{number}_mean"] = np.asarray(moving_mean, dtype=np.float32)
        arrays[f"bn{number}_variance"] = np.asarray(moving_variance, dtype=np.float32)

    dense_kernel, dense_bias = model.get_layer("dense").get_weights()
    output_kernel, output_bias = model.get_layer("dense_1").get_weights()
    arrays["dense1_kernel"] = np.asarray(dense_kernel, dtype=np.float32)
    arrays["dense1_bias"] = np.asarray(dense_bias, dtype=np.float32)
    arrays["output_kernel"] = np.asarray(output_kernel, dtype=np.float32)
    arrays["output_bias"] = np.asarray(output_bias, dtype=np.float32)
    arrays["batch_norm_epsilon"] = np.asarray(
        model.get_layer("batch_normalization").epsilon,
        dtype=np.float32,
    )
    np.savez_compressed(path, **arrays)


def save_confusion_matrix(matrix: np.ndarray, classes: list[str], path: Path) -> None:
    """Save a labelled CNN confusion matrix."""
    figure = plt.figure(figsize=(12, 10))
    plt.imshow(matrix, interpolation="nearest", cmap="Blues")
    plt.title("CNN Confusion Matrix")
    plt.colorbar()
    ticks = np.arange(len(classes))
    plt.xticks(ticks, classes, rotation=90)
    plt.yticks(ticks, classes)
    plt.xlabel("Predicted label")
    plt.ylabel("Actual label")
    plt.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def save_history(history: tf.keras.callbacks.History, path: Path) -> None:
    """Save the training and validation history graph."""
    figure = plt.figure(figsize=(9, 6))
    plt.plot(history.history.get("accuracy", []), label="Training accuracy")
    plt.plot(history.history.get("val_accuracy", []), label="Validation accuracy")
    plt.plot(history.history.get("loss", []), label="Training loss")
    plt.plot(history.history.get("val_loss", []), label="Validation loss")
    plt.xlabel("Epoch")
    plt.ylabel("Value")
    plt.title("CNN Training History")
    plt.legend()
    plt.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_evaluation_files(
    output_dir: Path,
    metrics: dict,
    report: str,
    classes: list[str],
    norm_factor: float,
) -> None:
    """Write the text report, JSON metrics, and runtime metadata."""
    (output_dir / "CNN_Evaluation_Metrics.txt").write_text(
        "CNN Landmark Model Evaluation\n"
        f"Accuracy: {metrics['accuracy']:.4f}\n"
        f"Precision (weighted): {metrics['precision_weighted']:.4f}\n"
        f"Recall (weighted): {metrics['recall_weighted']:.4f}\n"
        f"F1 Score (weighted): {metrics['f1_weighted']:.4f}\n"
        f"Epochs completed: {metrics['epochs_completed']}\n\n"
        f"Classification Report:\n{report}",
        encoding="utf-8",
    )
    (output_dir / "evaluation_metrics.json").write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )
    (output_dir / "cnn_metadata.json").write_text(
        json.dumps({"classes": classes, "normalization_factor": norm_factor}, indent=2),
        encoding="utf-8",
    )


def train(data_path: Path, output_dir: Path, epochs: int, batch_size: int) -> None:
    """Train with early stopping, evaluate the model, and save the outputs."""
    if not data_path.exists():
        raise FileNotFoundError(f"Processed dataset was not found: {data_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "CNN_Model_Improved.h5"
    runtime_path = output_dir / "CNN_Runtime_Weights.npz"

    x, y, classes, norm_factor = load_data(data_path)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.30,
        stratify=y,
        random_state=42,
    )

    model = build_model(len(classes))
    history = model.fit(
        x_train,
        y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.10,
        verbose=2,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=7,
                restore_best_weights=True,
            ),
            tf.keras.callbacks.ModelCheckpoint(
                str(model_path),
                monitor="val_loss",
                save_best_only=True,
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=3,
                min_lr=1e-6,
            ),
        ],
    )

    probabilities = model.predict(x_test, verbose=0)
    predictions = np.argmax(probabilities, axis=1)
    labels = list(range(len(classes)))
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision_weighted": float(
            precision_score(y_test, predictions, average="weighted", zero_division=0)
        ),
        "recall_weighted": float(
            recall_score(y_test, predictions, average="weighted", zero_division=0)
        ),
        "f1_weighted": float(
            f1_score(y_test, predictions, average="weighted", zero_division=0)
        ),
        "normalization_factor": norm_factor,
        "epochs_completed": len(history.history.get("loss", [])),
        "classes": classes,
    }
    report = classification_report(
        y_test,
        predictions,
        labels=labels,
        target_names=classes,
        zero_division=0,
    )

    write_evaluation_files(output_dir, metrics, report, classes, norm_factor)
    save_confusion_matrix(
        confusion_matrix(y_test, predictions, labels=labels),
        classes,
        output_dir / "CNN_Confusion_Matrix.png",
    )
    save_history(history, output_dir / "CNN_Training_History.png")
    model.save(str(model_path))
    export_runtime_weights(model, runtime_path)

    print(f"Keras model saved: {model_path}")
    print(f"Desktop runtime weights saved: {runtime_path}")
    print(f"Evaluation report saved: {output_dir / 'CNN_Evaluation_Metrics.txt'}")


def parse_args() -> argparse.Namespace:
    """Read the training paths and settings from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    """Run CNN training with the chosen settings."""
    args = parse_args()
    train(args.data.resolve(), args.output_dir.resolve(), args.epochs, args.batch_size)


if __name__ == "__main__":
    main()
