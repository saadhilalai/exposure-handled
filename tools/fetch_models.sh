#!/bin/sh
# Download the face models from the OpenCV model zoo and verify them.
# YuNet face detector (MIT license).
set -e
cd "$(dirname "$0")/.."
# sha256sum on Linux (the Pi), shasum on the Mac
if command -v sha256sum >/dev/null; then CHECK="sha256sum -c -"; else CHECK="shasum -a 256 -c -"; fi
mkdir -p models
URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SHA="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
curl -sL -o models/face_detection_yunet_2023mar.onnx "$URL"
echo "$SHA  models/face_detection_yunet_2023mar.onnx" | $CHECK

# SFace face signatures for "this face looks right" (Apache 2.0, OpenCV model zoo).
URL="https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
SHA="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
curl -sL -o models/face_recognition_sface_2021dec.onnx "$URL"
echo "$SHA  models/face_recognition_sface_2021dec.onnx" | $CHECK
