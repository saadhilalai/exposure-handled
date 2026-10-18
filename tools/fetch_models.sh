#!/bin/sh
# Download the YuNet face detector (MIT license, OpenCV model zoo) and verify it.
set -e
cd "$(dirname "$0")/.."
mkdir -p models
URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SHA="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
curl -sL -o models/face_detection_yunet_2023mar.onnx "$URL"
echo "$SHA  models/face_detection_yunet_2023mar.onnx" | shasum -a 256 -c -
