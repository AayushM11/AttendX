import numpy as np
import json
import cv2
import os
import time
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from models import FaceEmbedding, Employee

#  Thresholds 
RECOGNITION_THRESHOLD = 0.40
DUPLICATE_THRESHOLD   = 0.50
MAX_IMAGE_DIM         = 800

# Expected minimum size of a valid facenet_weights.h5 (bytes)
# Real file is ~92MB — if smaller, it's corrupted
FACENET_MIN_SIZE_BYTES = 80 * 1024 * 1024   # 80 MB minimum


#  Base directory 
def _find_base_dir() -> str:
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        if os.path.isdir(os.path.join(current, "uploaded_images")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = _find_base_dir()
print(f"[Recognition] BASE_DIR={BASE_DIR}")


#  Weights integrity check 

def _weights_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".deepface", "weights", "facenet_weights.h5")


def _check_and_fix_weights() -> bool:
    """
    Check if facenet_weights.h5 exists and is not corrupted.
    If corrupted → delete it so DeepFace re-downloads on next call.
    Returns True if weights are OK, False if deleted (needs re-download).
    """
    path = _weights_path()

    if not os.path.exists(path):
        print("[Recognition] Facenet weights not found — will download on first use.")
        return False

    size = os.path.getsize(path)
    if size < FACENET_MIN_SIZE_BYTES:
        print(f"[Recognition] ⚠ Corrupted weights detected! Size={size/1024/1024:.1f}MB (expected ~92MB)")
        print(f"[Recognition] Deleting corrupted file: {path}")
        try:
            os.remove(path)
            print("[Recognition] Deleted. Will re-download on next use.")
        except Exception as e:
            print(f"[Recognition] Cannot delete corrupted file: {e}")
            print(f"[Recognition] Please manually delete: {path}")
        return False

    print(f"[Recognition] Weights OK ({size/1024/1024:.1f}MB) ✅")
    return True


#  Model cache 
_facenet_model = None

def _get_model():
    global _facenet_model
    if _facenet_model is None:
        # Check weights before attempting to load
        weights_ok = _check_and_fix_weights()
        if not weights_ok:
            print("[Recognition] Weights missing/deleted — DeepFace will download now...")
            print("[Recognition] This may take 1-5 minutes depending on connection speed.")
            print("[Recognition] DO NOT interrupt the server during download.")

        print("[Recognition] Loading Facenet model into memory...")
        t = time.time()
        try:
            from deepface import DeepFace
            _facenet_model = DeepFace.build_model("Facenet")
            elapsed = time.time() - t

            # Verify it actually loaded by checking the weights file size now
            path = _weights_path()
            if os.path.exists(path):
                size = os.path.getsize(path)
                if size < FACENET_MIN_SIZE_BYTES:
                    # Download happened but file is still small — interrupted again
                    os.remove(path)
                    raise RuntimeError(
                        f"Facenet weights downloaded but corrupted ({size/1024/1024:.1f}MB). "
                        f"Internet may have been interrupted. Restart server to retry."
                    )

            print(f"[Recognition] Facenet ready in {elapsed:.1f}s ✅")

        except Exception as e:
            _facenet_model = None   # reset so next call retries
            raise RuntimeError(f"Failed to load Facenet model: {e}")

    return _facenet_model


def warmup():
    """Call once at server startup to pre-load model and validate weights."""
    try:
        _get_model()
    except RuntimeError as e:
        print(f"[Recognition] ❌ Warmup failed: {e}")
        print("[Recognition] Continuing without face recognition — register will fail until fixed.")
    except Exception as e:
        print(f"[Recognition] ❌ Warmup unexpected error: {e}")


#  Image helpers 

def _fix_exif(img_bgr: np.ndarray, image_path: str) -> np.ndarray:
    try:
        import PIL.Image
        with PIL.Image.open(image_path) as p:
            orientation = p.getexif().get(274)
        rotations = {3: cv2.ROTATE_180, 6: cv2.ROTATE_90_CLOCKWISE, 8: cv2.ROTATE_90_COUNTERCLOCKWISE}
        if orientation in rotations:
            img_bgr = cv2.rotate(img_bgr, rotations[orientation])
    except Exception:
        pass
    return img_bgr


def _enhance(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2RGB)


def _resize(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    if max(h, w) > MAX_IMAGE_DIM:
        scale = MAX_IMAGE_DIM / max(h, w)
        rgb = cv2.resize(rgb, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return rgb


def load_and_prepare(image_path: str) -> Optional[np.ndarray]:
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        return None
    img_bgr = _fix_exif(img_bgr, image_path)
    return _resize(_enhance(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))


def load_image_from_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return None
    return _resize(_enhance(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)))


#  Core embedding 

DETECTOR_ORDER = ["mtcnn", "ssd", "opencv"]

def _embed(rgb: np.ndarray) -> Optional[List[float]]:
    from deepface import DeepFace
    _get_model()   # ensure model loaded and weights valid

    rotations = [
        rgb,
        cv2.rotate(rgb, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(rgb, cv2.ROTATE_90_COUNTERCLOCKWISE),
        cv2.rotate(rgb, cv2.ROTATE_180),
    ]

    for backend in DETECTOR_ORDER:
        for img in rotations:
            try:
                results = DeepFace.represent(
                    img_path          = img,
                    model_name        = "Facenet",
                    detector_backend  = backend,
                    enforce_detection = True,
                    align             = True,
                )
                if results:
                    vec  = np.array(results[0]["embedding"], dtype=np.float64)
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                    print(f"[embed] ✅ Detected with backend={backend}")
                    return vec.tolist()
            except ValueError:
                continue
            except Exception as e:
                err = str(e)
                if "facenet_weights" in err or "pre-trained weights" in err:
                    # Weights corrupted — delete and raise so caller knows
                    print(f"[embed] ❌ Corrupted weights detected during embedding!")
                    path = _weights_path()
                    if os.path.exists(path):
                        os.remove(path)
                        print(f"[embed] Deleted corrupted weights. Restart server to re-download.")
                    raise RuntimeError(
                        "Facenet weights file is corrupted. "
                        "Server has been restarted automatically — please try again in 2 minutes."
                    )
                print(f"[embed] backend={backend} error: {e}")
                continue

    return None


def encode_face_from_path(image_path: str) -> Optional[List[float]]:
    if not os.path.exists(image_path):
        print(f"[encode] Not found: {image_path}")
        return None
    try:
        rgb = load_and_prepare(image_path)
        if rgb is None:
            return None
        result = _embed(rgb)
        if result is None:
            print(f"[encode] No face detected: {os.path.basename(image_path)}")
        return result
    except RuntimeError as e:
        raise   # re-raise weights corruption error to caller
    except Exception as e:
        print(f"[encode] Error {image_path}: {e}")
        return None


def encode_face_from_bytes(image_bytes: bytes) -> Tuple[Optional[List[float]], str]:
    try:
        rgb = load_image_from_bytes(image_bytes)
        if rgb is None:
            return None, "error"
        enc = _embed(rgb)
        return (enc, "ok") if enc else (None, "no_face")
    except Exception as e:
        print(f"[encode_bytes] Error: {e}")
        return None, "error"


#  Distance helper 

def _cosine_distances(incoming: np.ndarray, stored_vecs: List[np.ndarray]) -> np.ndarray:
    return 1.0 - (np.stack(stored_vecs) @ incoming)


#  Duplicate face check 

def check_duplicate_face(
    face_photos_rgb: List[np.ndarray],
    db: Session,
) -> Tuple[bool, Optional[str], Optional[str]]:
    all_embeddings = (
        db.query(FaceEmbedding)
        .join(Employee)
        .filter(Employee.is_active == True)
        .all()
    )
    if not all_embeddings:
        return False, None, None

    stored_vecs, emp_db_ids = [], []
    for emb in all_embeddings:
        try:
            stored_vecs.append(np.array(json.loads(emb.embedding), dtype=np.float64))
            emp_db_ids.append(emb.employee_id)
        except Exception:
            continue

    if not stored_vecs:
        return False, None, None

    for i, rgb in enumerate(face_photos_rgb):
        try:
            encoding = _embed(rgb)
        except Exception:
            continue
        if encoding is None:
            continue

        incoming  = np.array(encoding, dtype=np.float64)
        distances = _cosine_distances(incoming, stored_vecs)

        employee_distances: dict = {}
        for emp_db_id, dist in zip(emp_db_ids, distances):
            employee_distances.setdefault(emp_db_id, []).append(float(dist))

        for emp_db_id, dists in employee_distances.items():
            dists.sort()
            best = float(np.mean(dists[:min(3, len(dists))]))
            print(f"[DupCheck] photo_{i+1} vs {emp_db_id}  score={best:.4f}")
            if best < DUPLICATE_THRESHOLD:
                emp = db.query(Employee).filter(Employee.employee_id == emp_db_id).first()
                if emp:
                    print(f"[DupCheck] ❌ Duplicate: {emp.full_name} ({emp.employee_id})")
                    return True, emp.employee_id, emp.full_name

    return False, None, None


#  Attendance recognition 

def recognize_face(image_bytes: bytes, db: Session) -> Tuple[Optional[int], Optional[str], str]:
    encoding, status = encode_face_from_bytes(image_bytes)
    if status != "ok":
        return None, None, status

    all_embeddings = (
        db.query(FaceEmbedding)
        .join(Employee)
        .filter(Employee.is_active == True)
        .all()
    )
    if not all_embeddings:
        print("[Recognition] No embeddings in DB.")
        return None, None, "unknown"

    incoming = np.array(encoding, dtype=np.float64)

    stored_vecs, emp_ids = [], []
    for emb in all_embeddings:
        try:
            stored_vecs.append(np.array(json.loads(emb.embedding), dtype=np.float64))
            emp_ids.append(emb.employee_id)
        except Exception:
            continue

    if not stored_vecs:
        return None, None, "unknown"

    distances = _cosine_distances(incoming, stored_vecs)

    employee_distances: dict = {}
    for emp_id, dist in zip(emp_ids, distances):
        employee_distances.setdefault(emp_id, []).append(float(dist))

    best_id, best_score = None, float("inf")
    for emp_id, dists in employee_distances.items():
        dists.sort()
        avg = float(np.mean(dists[:min(3, len(dists))]))
        if avg < best_score:
            best_score, best_id = avg, emp_id

    print(f"[Recognition] best={best_id}  score={best_score:.4f}  threshold={RECOGNITION_THRESHOLD}")

    if best_id is not None and best_score < RECOGNITION_THRESHOLD:
        emp = db.query(Employee).filter(Employee.id == best_id).first()
        if emp:
            print(f"[Recognition] ✅ {emp.full_name}")
            return emp.id, emp.full_name, "matched"

    print("[Recognition] ❌ No match")
    return None, None, "unknown"


#  Batch embedding generation 

def generate_embeddings_for_employee(employee_db_id: int, db: Session) -> dict:
    t0 = time.time()

    employee = db.query(Employee).filter(Employee.id == employee_db_id).first()
    if not employee:
        return {"success": False, "message": "Employee not found"}

    upload_dir = os.path.join(BASE_DIR, "uploaded_images", employee.employee_id)
    print(f"[Embedding] {employee.employee_id} → {upload_dir}")

    if not os.path.exists(upload_dir):
        return {"success": False, "message": f"No images folder at {upload_dir}"}

    image_files = sorted([
        os.path.join(upload_dir, f)
        for f in os.listdir(upload_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    print(f"[Embedding] {len(image_files)} image(s)")

    if not image_files:
        return {"success": False, "message": "No image files found"}

    # Clear old embeddings
    try:
        db.query(FaceEmbedding).filter(FaceEmbedding.employee_id == employee_db_id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Embedding] Could not clear old embeddings: {e}")

    success_count = failed_count = 0

    for img_path in image_files:
        fname = os.path.basename(img_path)
        t1    = time.time()
        try:
            encoding = encode_face_from_path(img_path)
            if encoding:
                emb = FaceEmbedding(
                    employee_id = employee_db_id,
                    embedding   = json.dumps(encoding),
                    image_path  = img_path,
                )
                db.add(emb)
                db.commit()
                db.refresh(emb)
                success_count += 1
                print(f"[Embedding] ✅ {fname}  id={emb.id}  {time.time()-t1:.1f}s")
            else:
                failed_count += 1
                print(f"[Embedding] ⚠ No face in {fname}  {time.time()-t1:.1f}s")
        except RuntimeError as e:
            # Weights corrupted mid-run
            return {
                "success":         False,
                "message":         str(e),
                "embeddings_count": success_count,
                "failed_count":    failed_count + (len(image_files) - success_count - failed_count),
                "elapsed_seconds": round(time.time() - t0, 1),
            }
        except Exception as e:
            db.rollback()
            failed_count += 1
            print(f"[Embedding] ❌ {fname}: {e}")

    elapsed = time.time() - t0
    print(f"[Embedding] Done {elapsed:.1f}s — {success_count} saved, {failed_count} skipped")

    if success_count == 0:
        return {
            "success":          False,
            "message":          "No faces detected. Use good lighting, face clearly visible.",
            "embeddings_count": 0,
            "failed_count":     failed_count,
            "elapsed_seconds":  round(elapsed, 1),
        }

    return {
        "success":          True,
        "message":          f"Generated {success_count} embedding(s) in {elapsed:.1f}s",
        "embeddings_count": success_count,
        "failed_count":     failed_count,
        "elapsed_seconds":  round(elapsed, 1),
    }