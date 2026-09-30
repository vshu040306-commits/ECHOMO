# ECHOMO: Emotion-Driven Audio Installation

This repository contains the core source code and models for **ECHOMO**, an interactive acoustic installation that translates real-time facial expressions into dynamic audio modulation.

## Tech Stack
* **Computer Vision:** MediaPipe (Face Mesh / 52 Blendshapes)
* **Machine Learning:** Edge Impulse (Custom MLP Classifier, 89.8% Validation Accuracy)
* **Audio DSP:** Python (Spotify's Pedalboard library)
* **Hardware:** Arduino UNO, Gesture Sensors, LED Shield

## Core Modules & Models
1. `emorecog.py`: Captures video stream, extracts facial blendshapes via MediaPipe, runs local AI inference, and outputs emotion states.
2. `audioeh2.0.py`: Reads emotion data, dynamically modulates audio DSP parameters, and manages serial communication with the hardware.
3. `arduino_control.ino`: Handles hardware debouncing, receives serial commands from Python, and controls the ambient LED animation loop based on gesture inputs.
4. `echomo.h5`: The custom-trained neural network model weights (exported via Edge Impulse) for emotion classification.
5. `face_landmarker.task`: The pre-trained MediaPipe face landmark detection model used for blendshape extraction.

## Live AI Project
* **Dataset & Model Pipeline:** [View full project on Edge Impulse](https://studio.edgeimpulse.com/public/743578/live)

> **Note:** This repository serves as the technical appendix for my design portfolio.
