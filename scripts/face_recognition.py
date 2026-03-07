"""
Face Recognition Module — Detect, embed, and cluster faces across photos.
Uses OpenCV Haar cascades for detection, HOG descriptors for embeddings,
and agglomerative clustering with cosine distance for grouping.
"""
import os
import cv2
import numpy as np

# Face detection settings
FACE_SCALE_FACTOR = 1.1
FACE_MIN_NEIGHBORS = 5
FACE_MIN_SIZE = (30, 30)
FACE_MAX_IMAGE_WIDTH = 2000
FACE_CLUSTERING_THRESHOLD = 0.45

# Initialize Haar cascade (loaded once)
_cascade_path = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
_face_cascade = cv2.CascadeClassifier(_cascade_path)
_hog = cv2.HOGDescriptor()


def detect_faces(filepath):
    """Detect face bounding boxes in an image. Returns list of (x, y, w, h) tuples."""
    try:
        img = cv2.imread(filepath)
        if img is None:
            return [], None
    except Exception:
        return [], None

    h, w = img.shape[:2]
    scale = 1.0
    if w > FACE_MAX_IMAGE_WIDTH:
        scale = FACE_MAX_IMAGE_WIDTH / w
        img = cv2.resize(img, (FACE_MAX_IMAGE_WIDTH, int(h * scale)))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = _face_cascade.detectMultiScale(
        gray,
        scaleFactor=FACE_SCALE_FACTOR,
        minNeighbors=FACE_MIN_NEIGHBORS,
        minSize=FACE_MIN_SIZE,
    )

    if len(faces) == 0:
        return [], gray

    # Convert back to original image coordinates if we resized
    if scale < 1.0:
        faces = [(int(x / scale), int(y / scale), int(fw / scale), int(fh / scale))
                 for x, y, fw, fh in faces]
    else:
        faces = [(int(x), int(y), int(fw), int(fh)) for x, y, fw, fh in faces]

    return faces, gray


def extract_embedding(filepath, face_bbox):
    """Extract a normalized HOG descriptor from a face region."""
    try:
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
    except Exception:
        return None

    x, y, w, h = face_bbox
    ih, iw = img.shape[:2]

    # Clamp to image bounds
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(iw, x + w)
    y2 = min(ih, y + h)

    if x2 - x1 < 10 or y2 - y1 < 10:
        return None

    face_crop = img[y1:y2, x1:x2]
    face_resized = cv2.resize(face_crop, (64, 128))

    try:
        descriptor = _hog.compute(face_resized)
    except Exception:
        return None

    if descriptor is None or descriptor.size == 0:
        return None

    descriptor = descriptor.flatten().astype(np.float32)
    norm = np.linalg.norm(descriptor)
    if norm > 0:
        descriptor = descriptor / norm

    return descriptor


def cosine_distance_matrix(embeddings):
    """Compute pairwise cosine distance matrix. Returns NxN numpy array."""
    E = np.array(embeddings, dtype=np.float32)
    similarity = E @ E.T
    # Clamp to [-1, 1] to avoid numerical issues
    similarity = np.clip(similarity, -1.0, 1.0)
    return 1.0 - similarity


def agglomerative_cluster(distance_matrix, threshold):
    """Simple agglomerative clustering (average linkage) using a distance matrix.
    Returns list of cluster labels (0-indexed)."""
    n = distance_matrix.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [0]

    # Each point starts as its own cluster
    labels = list(range(n))
    # Track which points belong to each cluster
    clusters = {i: [i] for i in range(n)}
    # Work with a copy of the distance matrix
    dist = distance_matrix.copy()
    np.fill_diagonal(dist, np.inf)

    active = set(range(n))

    while len(active) > 1:
        # Find the closest pair of active clusters
        min_dist = np.inf
        merge_a, merge_b = -1, -1

        active_list = sorted(active)
        for i_idx, a in enumerate(active_list):
            for b in active_list[i_idx + 1:]:
                if dist[a][b] < min_dist:
                    min_dist = dist[a][b]
                    merge_a, merge_b = a, b

        if min_dist > threshold or merge_a < 0:
            break

        # Merge cluster b into cluster a
        points_a = clusters[merge_a]
        points_b = clusters[merge_b]

        # Update distances using average linkage
        for c in active:
            if c == merge_a or c == merge_b:
                continue
            # Average distance between merged cluster and cluster c
            total = 0.0
            count = 0
            for pa in points_a:
                for pc in clusters[c]:
                    total += distance_matrix[pa][pc]
                    count += 1
            for pb in points_b:
                for pc in clusters[c]:
                    total += distance_matrix[pb][pc]
                    count += 1
            avg_dist = total / count if count > 0 else np.inf
            dist[merge_a][c] = avg_dist
            dist[c][merge_a] = avg_dist

        # Merge point lists
        clusters[merge_a] = points_a + points_b
        del clusters[merge_b]
        active.discard(merge_b)

        # Invalidate merge_b row/col
        dist[merge_b, :] = np.inf
        dist[:, merge_b] = np.inf

    # Assign final labels
    result_labels = [0] * n
    for cluster_id, (_, points) in enumerate(sorted(clusters.items())):
        for p in points:
            result_labels[p] = cluster_id

    return result_labels


def process_all_faces(file_list, threshold=FACE_CLUSTERING_THRESHOLD, progress_callback=None):
    """Main entry point: detect faces, extract embeddings, cluster, and return results.

    Returns:
        dict: filepath -> {'face_count': int, 'person_names': str, 'face_bboxes': list}
    """
    # Phase 1: Detect faces and extract embeddings
    all_faces = []  # list of (filepath, bbox_index, embedding)
    file_face_map = {}  # filepath -> list of bbox

    total = len(file_list)
    for i, filepath in enumerate(file_list):
        if progress_callback and ((i + 1) % 50 == 0 or i == 0):
            progress_callback(i + 1, total, os.path.basename(filepath))

        faces, _ = detect_faces(filepath)
        file_face_map[filepath] = faces

        for bbox_idx, bbox in enumerate(faces):
            emb = extract_embedding(filepath, bbox)
            if emb is not None:
                all_faces.append((filepath, bbox_idx, emb))

    if progress_callback:
        progress_callback(total, total, "done")

    # Phase 2: Cluster embeddings
    if len(all_faces) == 0:
        return {fp: {'face_count': len(bboxes), 'person_names': '', 'face_bboxes': bboxes}
                for fp, bboxes in file_face_map.items()}

    embeddings = [f[2] for f in all_faces]
    dist_matrix = cosine_distance_matrix(embeddings)
    cluster_labels = agglomerative_cluster(dist_matrix, threshold)

    # Phase 3: Sort clusters by frequency (most common person = Person_1)
    from collections import Counter
    label_counts = Counter(cluster_labels)
    # Map old label -> new label (sorted by frequency descending)
    sorted_labels = [lbl for lbl, _ in label_counts.most_common()]
    label_remap = {old: new_idx for new_idx, old in enumerate(sorted_labels)}

    # Phase 4: Build per-file results
    face_to_person = {}
    for idx, (filepath, bbox_idx, _) in enumerate(all_faces):
        person_id = label_remap[cluster_labels[idx]] + 1  # 1-indexed
        key = (filepath, bbox_idx)
        face_to_person[key] = f"Person_{person_id}"

    results = {}
    for filepath, bboxes in file_face_map.items():
        face_count = len(bboxes)
        persons = []
        for bbox_idx in range(len(bboxes)):
            key = (filepath, bbox_idx)
            if key in face_to_person:
                persons.append(face_to_person[key])

        # Deduplicate and sort
        unique_persons = sorted(set(persons), key=lambda p: int(p.split('_')[1]))
        person_names = ', '.join(unique_persons) if unique_persons else ''

        results[filepath] = {
            'face_count': face_count,
            'person_names': person_names,
            'face_bboxes': bboxes,
        }

    # Fill in files with no faces
    for filepath in file_list:
        if filepath not in results:
            results[filepath] = {'face_count': 0, 'person_names': '', 'face_bboxes': []}

    return results
