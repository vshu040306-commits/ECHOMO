import cv2
import mediapipe as mp
import numpy as np
import os
import time
import tensorflow as tf

# --- 模型配置 ---
H5_MODEL_PATH = 'echomo.h5'
LABELS = ["aggressive", "enjoyed", "floating", "followbeats", "happy", "immersed", "neutral", "sad", "sad2", "scream"]

try:
    model = tf.keras.models.load_model(H5_MODEL_PATH)
    print(f"成功加载模型: {H5_MODEL_PATH}")
except Exception as e:
    print(f"错误：加载模型失败。请确保 TensorFlow 已安装，且模型文件路径正确。")
    print(e)
    exit()

# --- MediaPipe 初始化 ---
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode
mp_model_path = 'face_landmarker.task'

if not os.path.exists(mp_model_path):
    print(f"错误: MediaPipe模型 '{mp_model_path}' 未找到。")
    exit()

options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=mp_model_path),
    running_mode=RunningMode.VIDEO,
    output_face_blendshapes=True,
    num_faces=1
)

# 直接使用摄像头采集模式
cap = cv2.VideoCapture(0)

print("开始表情识别。按 'q' 键退出。")

# 初始化时间零点
start_time = time.time()

# 打开文本文件用于记录
with open('emotion_log.txt', 'w') as log_file:
    with FaceLandmarker.create_from_options(options) as landmarker:
        window_name = 'Emotion Recognition'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        while True:
            success, frame = cap.read()
            if not success:
                continue
            frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            frame_timestamp_ms = int((time.time() - start_time) * 1000)

            face_landmarker_result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

            annotated_image = frame
            if face_landmarker_result.face_landmarks and face_landmarker_result.face_blendshapes:
                features = [shape.score for shape in face_landmarker_result.face_blendshapes[0]]
                input_data = np.array([features], dtype=np.float32)

                # 在 predict 调用中加入 verbose=0
                predictions = model.predict(input_data, verbose=0)[0]

                emotion_index = np.argmax(predictions)
                emotion = LABELS[emotion_index]
                confidence = predictions[emotion_index]
                
                # 将当前情绪写入文件
                try:
                    with open('emotion.txt', 'w') as f:
                        f.write(emotion)
                except Exception as e:
                    print(f"写入情绪文件时出错: {e}")

                elapsed_time = time.time() - start_time
                log_entry = f"时间戳: {elapsed_time:.2f} 秒 -> 表情: {emotion}\n"
                log_file.write(log_entry)
                log_file.flush()  # 确保立即写入

                display_text = f"Emotion: {emotion} ({confidence:.2f})"
                cv2.putText(annotated_image, display_text,
                            (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

            # 实时预览
            cv2.imshow(window_name, annotated_image)

            if cv2.waitKey(5) & 0xFF == ord('q'):
                break

cap.release()
cv2.destroyAllWindows()
print("程序已退出。")