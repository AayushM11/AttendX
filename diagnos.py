import cv2
import numpy as np
import os
import sys

# ── Find a photo to test ─────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploaded_images")

test_images = []
if os.path.exists(UPLOAD_DIR):
    for emp_folder in os.listdir(UPLOAD_DIR):
        folder = os.path.join(UPLOAD_DIR, emp_folder)
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    test_images.append(os.path.join(folder, f))

if not test_images:
    print("❌ No images found in uploaded_images/")
    sys.exit(1)

test_img_path = test_images[0]
print(f"Testing with: {test_img_path}")
print("=" * 60)

# ── Load image ───────────────────────────────────────────────────────
img_bgr = cv2.imread(test_img_path)
if img_bgr is None:
    print("❌ Cannot load image with OpenCV")
    sys.exit(1)

h, w = img_bgr.shape[:2]
print(f"Image size: {w}x{h} pixels")
rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

# Resize to 800px max
if max(h, w) > 800:
    scale = 800 / max(h, w)
    rgb = cv2.resize(rgb, (int(w*scale), int(h*scale)))
    print(f"Resized to: {rgb.shape[1]}x{rgb.shape[0]}")

print()

# ── Test each DeepFace backend ───────────────────────────────────────
print("Testing DeepFace detectors...")
print("-" * 40)
try:
    from deepface import DeepFace

    backends = ["mtcnn", "opencv", "ssd", "retinaface", "mediapipe"]
    working_backends = []

    for backend in backends:
        try:
            import time
            t = time.time()
            result = DeepFace.represent(
                img_path          = rgb,
                model_name        = "Facenet",
                detector_backend  = backend,
                enforce_detection = True,
                align             = True,
            )
            elapsed = time.time() - t
            print(f"  ✅ {backend:<15} WORKS  ({elapsed:.1f}s)  embedding_len={len(result[0]['embedding'])}")
            working_backends.append(backend)
        except ValueError as e:
            print(f"  ❌ {backend:<15} No face detected")
        except Exception as e:
            print(f"  ⚠  {backend:<15} Error: {str(e)[:60]}")

    print()
    if working_backends:
        print(f"✅ Working backends: {working_backends}")
        print(f"   Best to use: {working_backends[0]}")
        print()
        print("ACTION: Open recognition.py and change DETECTOR_ORDER to:")
        print(f"   DETECTOR_ORDER = {working_backends}")
    else:
        print("❌ NO backend detected a face.")
        print()
        print("This means the image itself has an issue. Try:")
        print("  1. Check if the photo shows a clear frontal face")
        print("  2. Try with enforce_detection=False (see below)")

        # Try without enforcement to see if embedding works at all
        print()
        print("Testing with enforce_detection=False ...")
        try:
            result = DeepFace.represent(
                img_path          = rgb,
                model_name        = "Facenet",
                detector_backend  = "opencv",
                enforce_detection = False,
                align             = False,
            )
            print(f"  ✅ Works without detection — embedding generated")
            print("  → The image loads fine but no face is being located")
            print("  → Try: save the photo, open it in Photos app — is a face visible?")
        except Exception as e:
            print(f"  ❌ Even without detection fails: {e}")

except ImportError:
    print("❌ DeepFace not installed.")
    print("   Run: pip install deepface tf-keras mtcnn --break-system-packages")

print()
print("=" * 60)

# ── Also test with face_recognition (dlib) for comparison ───────────
print("Testing dlib (face_recognition) for comparison...")
print("-" * 40)
try:
    import face_recognition
    import time

    t    = time.time()
    locs = face_recognition.face_locations(rgb, model="hog")
    print(f"  HOG detector: {len(locs)} face(s) found in {time.time()-t:.1f}s")

    if locs:
        t   = time.time()
        enc = face_recognition.face_encodings(rgb, known_face_locations=locs[:1],
                                               num_jitters=1, model="small")
        print(f"  Encoding: {'✅ success' if enc else '❌ failed'}  ({time.time()-t:.1f}s)")
    else:
        print("  → dlib also cannot find a face in this image")
        print("  → The photo likely has orientation/format issue")

except ImportError:
    print("  face_recognition not installed (that's OK)")
except Exception as e:
    print(f"  Error: {e}")

print()
#print("Paste the output above in chat so I can see what's happening.")

