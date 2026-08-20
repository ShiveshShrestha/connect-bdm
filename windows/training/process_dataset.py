"""Convert an ASL image folder into MediaPipe landmark training data."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from tqdm import tqdm

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_DIR / "Processed_ASL_Dataset" / "Processed_ASL_Dataset_Train.npz"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def extract_landmarks(image: np.ndarray, detector) -> np.ndarray | None:
    """Read 63 values from the first detected hand, or return None."""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = detector.process(rgb)
    if not result.multi_hand_landmarks:
        return None

    hand = result.multi_hand_landmarks[0]
    return np.asarray(
        [value for landmark in hand.landmark for value in (landmark.x, landmark.y, landmark.z)],
        dtype=np.float32,
    )


def process_dataset(dataset_dir: Path, output_path: Path) -> None:
    """Process each class folder and save the usable hand landmarks in one NPZ file."""
    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset folder was not found: {dataset_dir}")

    class_dirs = sorted(path for path in dataset_dir.iterdir() if path.is_dir())
    if not class_dirs:
        raise ValueError("The dataset folder does not contain any class folders.")

    classes = [path.name for path in class_dirs]
    features: list[np.ndarray] = []
    labels: list[int] = []
    checked = 0
    detected = 0

    hands = mp.solutions.hands.Hands(
        static_image_mode=True,
        max_num_hands=1,
        min_detection_confidence=0.20,
    )
    try:
        for class_index, class_dir in enumerate(class_dirs):
            images = sorted(
                path for path in class_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS
            )
            print(f"{class_dir.name}: {len(images)} images")
            for image_path in tqdm(images, desc=class_dir.name, leave=False):
                checked += 1
                image = cv2.imread(str(image_path))
                if image is None:
                    continue
                vector = extract_landmarks(image, hands)
                if vector is not None:
                    features.append(vector)
                    labels.append(class_index)
                    detected += 1
    finally:
        hands.close()

    if not features:
        raise RuntimeError("No hand landmarks were found in the dataset images.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        X=np.asarray(features, dtype=np.float32),
        y=np.asarray(labels, dtype=np.int32),
        classes=np.asarray(classes),
    )

    print(f"Saved: {output_path}")
    print(f"Images checked: {checked}")
    print(f"Hands found: {detected}")
    print(f"Detection rate: {detected / checked * 100:.2f}%")


def parse_args() -> argparse.Namespace:
    """Read the dataset folder and output path from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        required=True,
        type=Path,
        help="Folder containing class folders such as A, B, C, del, nothing, and space.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output NPZ file.")
    return parser.parse_args()


def main() -> None:
    """Process the dataset with resolved input and output paths."""
    args = parse_args()
    process_dataset(args.dataset.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
