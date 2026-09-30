# ECHOMO: Emotion-Driven Audio Installation

This repository contains the core source code for **ECHOMO**, an interactive acoustic installation that translates real-time facial expressions into dynamic audio modulation.

## Tech Stack
* **Computer Vision:** MediaPipe (Face Mesh / 52 Blendshapes)
* **Machine Learning:** Edge Impulse (Custom MLP Classifier, 89.6% Validation Accuracy)
* **Audio DSP:** Python (Spotify's Pedalboard library)
* **Hardware:** Arduino UNO, Gesture Sensors, LED Shield

## Core Modules
1. `emorecog.py`: Captures video stream, extracts facial blendshapes via MediaPipe, runs local AI inference, and outputs emotion states.
2. `audioeh2.0.py`: Reads emotion data, dynamically modulates audio DSP parameters, and manages serial communication with the hardware.
3. `arduino_control.ino`: Handles hardware debouncing, receives serial commands from Python, and controls the ambient LED animation loop based on gesture inputs.

> **Note:** This repository serves as the technical appendix for my design portfolio.
