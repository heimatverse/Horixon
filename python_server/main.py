import cv2
import numpy as np
import base64
from deepface import DeepFace
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import logging
import logging.config
import mediapipe as mp
import uvicorn
from collections import defaultdict
from datetime import datetime
import csv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize background removal with mediapipe's SelfieSegmentation
segmentor = None

# Initialize variables
face_cascade = None

# Global dictionary to track detected faces
next_face_id = 0

# Emotion productivity weights (can be adjusted based on your needs)
emotion_weights = {
    "happy": 1.0,
    "neutral": 0.7,
    "surprise": 0.5,
    "sad": -0.5,
    "angry": -1.0,
    "fear": -0.8,
    "disgust": -0.7,
}

# CSV file path for storing face logs
csv_file_path = "logs/face_data.csv"


# Initialize the logging system
def setup_logging():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": "INFO",
            },
            "file_handler": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "level": "INFO",
                "filename": "logs/app_logs.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file_handler"],
                "level": "INFO",
                "propagate": True,
            }
        },
    }

    logging.config.dictConfig(logging_config)


# Create a logger for this module
logger = logging.getLogger(__name__)


def get_face_cascade():
    global face_cascade
    if face_cascade is None:
        # Initialize the Haar Cascade only when needed
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_alt.xml"
        )
    return face_cascade


def get_segmentor():
    global segmentor
    if segmentor is None:
        # Initialize SelfieSegmentation only when needed
        mp_selfie_segmentation = mp.solutions.selfie_segmentation
        segmentor = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
    return segmentor


# Initialize the CSV file by writing the headers if the file doesn't exist
def init_csv():
    try:
        with open(csv_file_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            file.seek(0)  # Move to the beginning of the file
            # if file.read(1):  # Check if the file is not empty (already has header)
            #     return
            # Write header if CSV is empty
            writer.writerow(
                [
                    "face_id",
                    "time_in",
                    "time_out",
                    "duration",
                    "emotions",
                    "productivity",
                ]
            )
        logger.info("CSV file initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing the CSV file: {e}")


# Function to insert face data into the CSV file
def insert_face_log(face_id, time_in, time_out, duration, emotions, productivity):
    try:
        with open(csv_file_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [time_in, time_out, face_id, duration, ",".join(emotions), productivity]
            )
        logger.info(f"Inserted face data for Face ID {face_id} into CSV file.")
    except Exception as e:
        logger.error(f"Error inserting face data into CSV: {e}")


def insert_face_emotion(currTime, faceId, detectedEmotion):
    try:
        with open(csv_file_path, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([currTime, faceId, detectedEmotion])
        logger.info(
            f"Logged emotion for Face ID {faceId} at {currTime}: {detectedEmotion}"
        )
    except Exception as e:
        logger.exception("Error inserting record into CSV.")


# Analyze face for emotion using DeepFace
def analyze_face(face_roi):
    try:
        result = DeepFace.analyze(
            face_roi, actions=["emotion"], enforce_detection=False
        )
        if isinstance(result, list):
            result = result[0]
        emotion = result.get("dominant_emotion")
        return emotion
    except Exception as e:
        logger.error(f"Error analyzing face: {e}")
        return None


# Function to calculate productivity based on emotions
def calculate_productivity(emotions):
    if not emotions:
        return 0.0
    weighted_sum = sum(emotion_weights.get(emotion, 0) for emotion in emotions)
    return max(
        0, min(100, (weighted_sum / len(emotions)) * 100)
    )  # Clamp between 0 and 100


# Function to match or assign a new face ID using DeepFace embeddings
def get_or_assign_face_id(face_roi):
    global next_face_id, face_ids

    # Get face embedding using DeepFace
    try:
        face_embedding = DeepFace.represent(face_roi, enforce_detection=False)[0][
            "embedding"
        ]

        # Try to match with existing face embeddings
        for face_id, data in face_ids.items():
            if (
                "embedding" in data
                and np.linalg.norm(
                    np.array(data["embedding"]) - np.array(face_embedding)
                )
                < 0.8
            ):
                return face_id

        maxKey = None

        if len(face_ids.keys()) > 0:
            maxKey = max(face_ids.keys())
        else:
            maxKey = 0

        # If no match, assign a new face ID
        face_ids[maxKey + 1] = {"embedding": face_embedding}

        return maxKey + 1
    except Exception as e:
        logger.error(f"Error extracting face embedding: {e}")
        return None


def is_base64(s: str) -> bool:
    try:
        base64.b64decode(s, validate=True)
        return True
    except Exception:
        return False


face_ids = {}  # Dictionary to store face embeddings and face IDs
face_data = defaultdict(lambda: {"time_in": None, "time_out": None, "emotions": []})


# Function to continuously capture frames from the camera
def capture_and_process_video(imageString: str) -> None:
    global face_ids, face_data
    detected_face_ids = set()

    isValidBaseString = is_base64(imageString)

    if not isValidBaseString:
        logger.error("Invalid base64 string provided.")
        return

    # Converting base64 string to np array
    try:
        image_data = base64.b64decode(imageString)
        np_array = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.exception("Error decoding image from base64 string.")
        return

    gray_frame = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Detect faces in the frame
    faces = face_cascade.detectMultiScale(
        gray_frame, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30)
    )

    logger.info(f"Faces found in image: {len(faces)}")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Process each detected face
    for x, y, w, h in faces:
        face_roi = image[y : y + h, x : x + w]
        face_id = get_or_assign_face_id(face_roi)

        if face_id is None:
            continue

        detected_face_ids.add(face_id)

        if face_data[face_id]["time_out"] is not None:
            face_data[face_id]["time_in"] = current_time
            face_data[face_id]["time_out"] = None
            face_data[face_id]["emotions"] = []

        if face_data[face_id]["time_in"] is None:
            face_data[face_id]["time_in"] = current_time

        # Analyze face for emotion
        emotion = analyze_face(face_roi)
        if emotion:
            face_data[face_id]["emotions"].append(emotion)
            insert_face_emotion(
                datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S"), face_id, emotion
            )
            logger.info(
                f"Face ID {face_id} detected emotion: {emotion} at {current_time}"
            )

    # Handle faces that are no longer detected
    for face_id in list(face_data.keys()):
        if face_id not in detected_face_ids:
            try:
                face_data[face_id]["time_out"] = current_time
                time_in = datetime.strptime(
                    face_data[face_id]["time_in"], "%Y-%m-%d %H:%M:%S"
                )
                time_out = datetime.strptime(current_time, "%Y-%m-%d %H:%M:%S")
                duration = (time_out - time_in).total_seconds()

                cumulative_emotions = face_data[face_id]["emotions"]
                productivity = calculate_productivity(cumulative_emotions)

                insert_face_log(
                    face_id,
                    face_data[face_id]["time_in"],
                    current_time,
                    duration,
                    cumulative_emotions,
                    productivity,
                )

                del face_data[face_id]
                logger.info(
                    f"Logged data for Face ID {face_id} and removed from tracking."
                )
            except Exception as e:
                logger.exception(f"Error processing face ID {face_id}: {e}")

    logger.debug(f"Current face data: {face_data}")
    logger.debug(f"Tracked face IDs: {list(face_ids.keys())}")


hasIntialised = False


@app.post("/process_frame")
async def process_frame(params: dict = Body(...)):
    global hasIntialised

    if not hasIntialised:
        setup_logging()
        get_face_cascade()
        get_segmentor()
        # init_csv()
        hasIntialised = True

    image = params.get("image")
    prefix1 = "data:image/jpeg;base64,"
    prefix2 = "data:image/png:base64,"
    prefix3 = "data:image/jpg:base64,"

    if image.startswith(prefix1):
        image = image[len(prefix1) :]

    if image.startswith(prefix2):
        image = image[len(prefix2) :]

    if image.startswith(prefix3):
        image = image[len(prefix3) :]

    try:
        capture_and_process_video(image)
        return {"message": "Frame processed successfully."}
    except Exception as e:
        logger.exception("Error processing frame.")
        raise HTTPException(status_code=500, detail="Failed to process the frame.")


@app.get("/")
async def read_root():
    return {"message": "Welcome to the FastAPI application!"}


# Middleware to handle exceptions globally
class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
            raise e


app.add_middleware(ExceptionLoggingMiddleware)

if __name__ == "__main__":
    setup_logging()
    uvicorn.run(app, host="0.0.0.0", port=8000)
