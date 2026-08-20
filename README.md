# Connect B-DM

Connect B-DM is an accessibility-focused communication platform built to help bridge communication gaps between people who use sign language, text, and speech.

The project combines machine learning, computer vision, speech processing, and application development in two implementations: a web application and a Windows desktop application.

## Project Overview

Connect B-DM focuses on three main communication workflows:

* **Sign to Text / Speech** — hand signs captured through a webcam are recognized and converted into readable text or spoken output.
* **Speech to Text** — recorded speech is converted into text for easier communication.
* **Text to Sign** — written text is represented using stored ASL alphabet images.

Both implementations explore the same core idea while using different application architectures and technologies.

## Implementations

| Version                          | Overview                                                                                                                                    | Main Technologies                                           |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| [Web Application](./web)         | Browser-based application with user accounts, sign recognition, speech recognition, text interpretation, and administrator controls.        | Python, Flask, MySQL, JavaScript, TensorFlow.js, MediaPipe  |
| [Windows Application](./windows) | Desktop application with voice-to-text, sign-to-voice, text-to-sign interpretation, CNN/KNN model selection, and keyboard-focused controls. | Python, Tkinter, MediaPipe, OpenCV, TensorFlow/Keras, NumPy |

Each version includes its own README with setup instructions, architecture details, workflows, model information, limitations, and usage guidance.

## Machine Learning

The sign-recognition system uses MediaPipe to detect and extract hand landmarks from webcam input.

For each detected hand:

* 21 landmarks are extracted.
* Each landmark provides `x`, `y`, and `z` coordinates.
* This produces a total of **63 input features** for classification.
* Supported classes include the ASL alphabet along with `del`, `nothing`, and `space`.

The Windows implementation includes both CNN and KNN models, making it possible to compare two different approaches to sign classification.

### Evaluation Results

The included models were evaluated on a held-out dataset containing **22,050 processed hand-landmark samples**.

| Model     | Accuracy | Weighted F1 |
| --------- | -------: | ----------: |
| CNN       |   99.15% |      99.15% |
| KNN (K=5) |   97.55% |      97.55% |

These results represent performance on the processed evaluation dataset.

Real-world webcam performance may vary depending on factors such as lighting, camera quality, hand position, background, distance from the camera, and differences between users.

## Repository Structure

```text
connect-bdm/
├── web/
│   ├── README.md
│   ├── app.py
│   ├── static/
│   └── templates/
│
├── windows/
│   ├── README.md
│   ├── Main.py
│   ├── Models/
│   ├── training/
│   └── Interpretation/
│
└── README.md
```

## Detailed Documentation

For installation instructions and implementation details, see:

* [Web Application Documentation](./web/README.md)
* [Windows Application Documentation](./windows/README.md)

## Project Scope

Connect B-DM was developed as an academic accessibility project to explore how machine learning, computer vision, speech processing, and software development can work together in a practical communication system.

The current sign-recognition component focuses on supported alphabet-style hand signs rather than continuous sign-language sentences.

The project is intended as a technical prototype and learning platform rather than a replacement for professional sign-language interpretation.
