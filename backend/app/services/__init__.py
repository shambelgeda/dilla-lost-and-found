from app.services.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    require_roles
)
from app.services.ai_engine import (
    generate_text_embedding,
    generate_image_embedding,
    cosine_similarity,
    compute_metadata_similarity,
    calculate_fusion_score,
    process_and_store_embedding,
    run_matching_engine_for_item
)
from app.services.notification import (
    send_match_notification,
    send_claim_update_notification
)
from app.services.privacy import (
    sanitize_item_out,
    sanitize_match_out,
    sanitize_claim_out
)

__all__ = [
    "verify_password", "get_password_hash", "create_access_token", "get_current_user", "get_current_user_optional", "require_roles",
    "generate_text_embedding", "generate_image_embedding", "cosine_similarity",
    "compute_metadata_similarity", "calculate_fusion_score", "process_and_store_embedding",
    "run_matching_engine_for_item", "send_match_notification", "send_claim_update_notification",
    "sanitize_item_out", "sanitize_match_out", "sanitize_claim_out"
]
