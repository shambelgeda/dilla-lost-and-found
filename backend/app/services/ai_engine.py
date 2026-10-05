import hashlib
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from app.config import settings
from app.models.item import Item, ItemType, ItemStatus, ItemEmbedding, ItemImage
from app.models.match import Match, MatchStatus
from app.models.location import CampusLocation

MODEL_VERSION = "multilingual-sim-v2"


def stable_bucket(value: str, dim: int) -> int:
    digest = hashlib.md5(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dim

# Common Amharic-English bilingual concept dictionary for Dilla University lost-and-found items
AMHARIC_ENGLISH_MAP = {
    "ላፕቶፕ": "laptop computer dell hp lenovo thinkpad acer asus macbook",
    "ኮምፒውተር": "computer pc laptop",
    "ስልክ": "phone mobile smartphone samsung iphone tecno infinix redmi huawei",
    "ሞባይል": "mobile smartphone phone",
    "መታወቂያ": "id card student identity badge credential card",
    "ካርድ": "card id atm student badge",
    "ቁልፍ": "key keys padlock lock keychain",
    "ቦርሳ": "bag backpack handbag wallet pouch case",
    "ዋሌት": "wallet purse cash card holder",
    "ጃኬት": "jacket coat sweater hoodie clothing",
    "ደብተር": "notebook book exercise book binder",
    "ፍላሽ": "flash drive usb memory stick thumb drive",
    "ሰዓት": "watch smartwatch wrist clock casio",
    "መነጽር": "glasses spectacles sunglasses eyewear"
}

def normalize_text(text: str) -> str:
    """Preprocess and clean text in English or Amharic."""
    if not text:
        return ""
    text = text.lower()
    # Expand Amharic keywords with contextual synonyms
    for amh, eng_exp in AMHARIC_ENGLISH_MAP.items():
        if amh in text:
            text += f" {eng_exp}"
    # Remove special punctuation
    text = re.sub(r"[^\w\s\u1200-\u137F]", " ", text)
    return text.strip()

def generate_text_embedding(text: str, dim: int = 512) -> List[float]:
    """
    Generate normalized 512-dimensional semantic vector for item text.
    Combines hashing vectorizer, character n-grams, and semantic term weighting.
    """
    cleaned = normalize_text(text)
    tokens = cleaned.split()
    if not tokens:
        vec = np.zeros(dim, dtype=np.float32)
        vec[0] = 1.0
        return vec.tolist()
    
    vec = np.zeros(dim, dtype=np.float32)
    
    # Semantic token hashing with n-grams
    for i, token in enumerate(tokens):
        # Unigram hash
        h1 = stable_bucket(token, dim)
        vec[h1] += 1.5
        
        # Bigram hash
        if i < len(tokens) - 1:
            bigram = f"{token}_{tokens[i+1]}"
            h2 = stable_bucket(bigram, dim)
            vec[h2] += 2.0
            
        # Character 3-grams for typo resilience & morphological matching
        for k in range(max(0, len(token) - 2)):
            tri = token[k:k+3]
            h3 = stable_bucket(tri, dim)
            vec[h3] += 0.5

    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return vec.tolist()

def generate_image_embedding(image_path: str, dim: int = 512) -> Optional[List[float]]:
    """
    Generate normalized 512-dimensional visual feature vector from an item photo.
    Extracts spatial color distributions (HSV/RGB), edge gradients, and perceptual block moments.
    """
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            # Resize to standard feature map size (64x64)
            img_thumb = img.resize((64, 64), Image.Resampling.BILINEAR)
            arr = np.array(img_thumb, dtype=np.float32) / 255.0  # (64, 64, 3)

            features = []
            
            # 1. Color channel histograms (64 bins per channel = 192 features)
            for c in range(3):
                hist, _ = np.histogram(arr[:, :, c], bins=64, range=(0.0, 1.0))
                features.extend(hist.astype(np.float32))

            # 2. Spatial 4x4 grid regional color averages (16 cells * 3 = 48 features)
            grid = arr.reshape(4, 16, 4, 16, 3).mean(axis=(1, 3)).flatten()
            features.extend(grid.astype(np.float32))

            # 3. Horizontal and vertical edge gradients (Sobel-like)
            dx = np.diff(arr, axis=1)[:, :-1, :] # (64, 62, 3)
            dy = np.diff(arr, axis=0)[:-1, :, :] # (62, 64, 3)
            grad_x_hist, _ = np.histogram(dx, bins=64, range=(-0.5, 0.5))
            grad_y_hist, _ = np.histogram(dy, bins=64, range=(-0.5, 0.5))
            features.extend(grad_x_hist.astype(np.float32))
            features.extend(grad_y_hist.astype(np.float32))

            # 4. Aspect ratio & brightness moment
            aspect_ratio = img.width / max(1, img.height)
            brightness = arr.mean()
            features.extend([aspect_ratio, brightness])

            feat_arr = np.array(features, dtype=np.float32)

            # Project or pad to exact `dim`
            if len(feat_arr) < dim:
                pad = np.zeros(dim - len(feat_arr), dtype=np.float32)
                vec = np.concatenate([feat_arr, pad])
            else:
                vec = feat_arr[:dim]

            # L2 normalize
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            else:
                vec[0] = 1.0
            return vec.tolist()
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two unit vectors (returns in range [0.0, 1.0])."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    dot = np.dot(a, b)
    # Clamp to [0, 1] range
    return float(max(0.0, min(1.0, dot)))

def compute_metadata_similarity(
    lost_item: Item, 
    found_item: Item,
    lost_loc: Optional[CampusLocation],
    found_loc: Optional[CampusLocation]
) -> float:
    """
    Compute metadata score based on:
    1. Category match (hard or strong affinity)
    2. Campus & block spatial proximity
    3. Chronological validity (found date should ideally be >= lost date)
    """
    # 1. Category check
    category_match = 1.0 if lost_item.category_id == found_item.category_id else 0.15
    if category_match < 0.2:
        return 0.05 # Strong penalty if categories completely disagree

    # 2. Location proximity
    loc_score = 0.2
    if lost_loc and found_loc:
        if lost_loc.id == found_loc.id:
            loc_score = 1.0 # Exact same block/room
        elif lost_loc.campus_name.strip().lower() == found_loc.campus_name.strip().lower():
            # Same campus (e.g. Main Campus or Odayaa Campus)
            loc_score = 0.65
        else:
            loc_score = 0.25 # Different campus site

    # 3. Temporal validity: Found date must logically be on or after lost date
    time_score = 1.0
    lost_dt = lost_item.incident_date
    found_dt = found_item.incident_date
    
    delta_days = (found_dt - lost_dt).total_seconds() / (24 * 3600)
    if delta_days < -1.0: # Found more than 24h before lost date -> highly improbable
        time_score = 0.1
    elif delta_days < 0:
        time_score = 0.6 # Minor clock skew / estimation uncertainty
    else:
        # Exponential decay for long gaps (e.g., found 1 year later is less likely than 3 days later)
        time_score = math.exp(-0.02 * min(delta_days, 90))

    meta_score = 0.5 * category_match + 0.3 * loc_score + 0.2 * time_score
    return round(float(meta_score), 4)

def calculate_fusion_score(
    image_sim: float, 
    text_sim: float, 
    meta_sim: float, 
    has_image: bool
) -> float:
    """
    Multimodal fusion with adaptive weighting:
    - If image is available: 45% image, 35% text, 20% metadata
    - If no image: 70% text, 30% metadata
    """
    if has_image and image_sim > 0.0:
        w_img = settings.WEIGHT_IMAGE
        w_txt = settings.WEIGHT_TEXT
        w_meta = settings.WEIGHT_METADATA
        total = (w_img * image_sim) + (w_txt * text_sim) + (w_meta * meta_sim)
    else:
        w_txt = 0.70
        w_meta = 0.30
        total = (w_txt * text_sim) + (w_meta * meta_sim)
    return round(float(min(1.0, max(0.0, total))), 4)

def process_and_store_embedding(item: Item, db: Session) -> ItemEmbedding:
    """Generate and persist vector embeddings for an item."""
    # Text embedding from title + description
    combined_text = f"{item.title} {item.description}"
    text_vec = generate_text_embedding(combined_text)

    # Image embedding
    image_vec = None
    if item.images and len(item.images) > 0:
        primary_img = item.images[0].file_path
        image_vec = generate_image_embedding(primary_img)

    existing_emb = db.query(ItemEmbedding).filter(ItemEmbedding.item_id == item.id).first()
    if existing_emb:
        existing_emb.text_vector_json = json.dumps(text_vec)
        existing_emb.image_vector_json = json.dumps(image_vec) if image_vec else None
        existing_emb.model_version = MODEL_VERSION
        existing_emb.generated_at = datetime.now(timezone.utc)
        emb = existing_emb
    else:
        emb = ItemEmbedding(
            id=f"emb-{item.id}",
            item_id=item.id,
            text_vector_json=json.dumps(text_vec),
            image_vector_json=json.dumps(image_vec) if image_vec else None,
            model_version=MODEL_VERSION,
            generated_at=datetime.now(timezone.utc)
        )
        db.add(emb)
    db.commit()
    db.refresh(emb)
    return emb

def run_matching_engine_for_item(target_item: Item, db: Session) -> List[Match]:
    """
    Execute AI matching pipeline for a newly submitted or updated item.
    - If target_item is LOST, scan all OPEN FOUND items.
    - If target_item is FOUND, scan all OPEN LOST items.
    """
    # Ensure target item has current embeddings
    target_emb = db.query(ItemEmbedding).filter(ItemEmbedding.item_id == target_item.id).first()
    if not target_emb or target_emb.model_version != MODEL_VERSION:
        target_emb = process_and_store_embedding(target_item, db)

    target_text_vec = json.loads(target_emb.text_vector_json)
    target_img_vec = json.loads(target_emb.image_vector_json) if target_emb.image_vector_json else None

    # Opposing pool
    opposing_type = ItemType.FOUND if target_item.report_type == ItemType.LOST else ItemType.LOST
    candidates = db.query(Item).filter(
        Item.report_type == opposing_type,
        Item.status == ItemStatus.OPEN,
        Item.id != target_item.id
    ).all()

    new_matches = []

    for candidate in candidates:
        cand_emb = db.query(ItemEmbedding).filter(ItemEmbedding.item_id == candidate.id).first()
        if not cand_emb or cand_emb.model_version != MODEL_VERSION:
            cand_emb = process_and_store_embedding(candidate, db)

        cand_text_vec = json.loads(cand_emb.text_vector_json)
        cand_img_vec = json.loads(cand_emb.image_vector_json) if cand_emb.image_vector_json else None

        # Text similarity
        text_sim = cosine_similarity(target_text_vec, cand_text_vec)

        # Image similarity
        has_both_images = (target_img_vec is not None) and (cand_img_vec is not None)
        image_sim = cosine_similarity(target_img_vec, cand_img_vec) if has_both_images else 0.0

        # Spatio-temporal metadata score
        lost_item = target_item if target_item.report_type == ItemType.LOST else candidate
        found_item = candidate if target_item.report_type == ItemType.LOST else target_item

        lost_loc = db.query(CampusLocation).filter(CampusLocation.id == lost_item.location_id).first()
        found_loc = db.query(CampusLocation).filter(CampusLocation.id == found_item.location_id).first()

        meta_sim = compute_metadata_similarity(lost_item, found_item, lost_loc, found_loc)

        # Fusion score
        final_score = calculate_fusion_score(image_sim, text_sim, meta_sim, has_image=has_both_images)

        # Threshold decision gate
        if final_score >= settings.THRESHOLD_OFFICER_REVIEW:
            match_status = MatchStatus.SUGGESTED if final_score >= settings.THRESHOLD_DIRECT_MATCH else MatchStatus.OFFICER_REVIEW

            # Check if match record already exists
            existing_match = db.query(Match).filter(
                Match.lost_item_id == lost_item.id,
                Match.found_item_id == found_item.id
            ).first()

            if existing_match:
                existing_match.image_score = image_sim
                existing_match.text_score = text_sim
                existing_match.meta_score = meta_sim
                existing_match.final_score = final_score
                existing_match.status = match_status
                new_matches.append(existing_match)
            else:
                match_id = f"mat-{uuid.uuid4().hex[:12]}"
                m = Match(
                    id=match_id,
                    lost_item_id=lost_item.id,
                    found_item_id=found_item.id,
                    image_score=image_sim,
                    text_score=text_sim,
                    meta_score=meta_sim,
                    final_score=final_score,
                    status=match_status,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(m)
                new_matches.append(m)

    db.commit()
    return new_matches


def refresh_stale_embeddings_and_matches(db: Session) -> None:
    """Rebuild embeddings that predate MODEL_VERSION, then re-run matching."""
    stale_exists = (
        db.query(ItemEmbedding)
        .filter(ItemEmbedding.model_version != MODEL_VERSION)
        .first()
        is not None
    )
    items = db.query(Item).all()
    missing_embeddings = any(
        db.query(ItemEmbedding).filter(ItemEmbedding.item_id == item.id).first() is None
        for item in items
    )
    if not items or (not stale_exists and not missing_embeddings):
        return

    for item in items:
        process_and_store_embedding(item, db)
    for item in items:
        run_matching_engine_for_item(item, db)
