import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db, sync_database_schema
from app.main import app
from app.models.category import Category
from app.models.claim import Claim, ClaimStatus
from app.models.item import Item, ItemType, ItemStatus
from app.models.location import CampusLocation
from app.models.match import Match, MatchStatus
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.services.auth import create_access_token, get_password_hash

SQLALCHEMY_DATABASE_URL = "sqlite:////tmp/dilla_lost_found_test.db"
if os.path.exists("/tmp/dilla_lost_found_test.db"):
    os.remove("/tmp/dilla_lost_found_test.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)
sync_database_schema(engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_public_registration_cannot_assign_privileged_role():
    response = client.post(
        f"{settings.API_V1_STR}/auth/register",
        json={
            "university_id": "DU/R/9001/14",
            "full_name": "New Student",
            "email": "new.student.9001@du.edu.et",
            "password": "safe-password-123",
            "role": "ADMIN",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["role"] == UserRole.STUDENT.value


def test_admin_can_provision_roles_but_students_cannot_manage_accounts():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        admin = User(
            id="usr-role-admin",
            university_id="DU/ADM/ROLE",
            full_name="Role Admin",
            email="role.admin@du.edu.et",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        student = User(
            id="usr-role-student",
            university_id="DU/R/ROLE/14",
            full_name="Role Student",
            email="role.student@du.edu.et",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([admin, student])
        db.commit()
        admin_token = create_access_token({"sub": admin.id, "role": admin.role.value})
        student_token = create_access_token({"sub": student.id, "role": student.role.value})
    finally:
        db.close()

    student_headers = {"Authorization": f"Bearer {student_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    assert client.get(f"{settings.API_V1_STR}/auth/users", headers=student_headers).status_code == 403
    assert client.patch(
        f"{settings.API_V1_STR}/auth/users/usr-role-student/role",
        json={"role": "SECURITY_OFFICER"},
        headers=student_headers,
    ).status_code == 403

    listing = client.get(f"{settings.API_V1_STR}/auth/users", headers=admin_headers)
    assert listing.status_code == 200
    assert all("hashed_password" not in account for account in listing.json())

    promotion = client.patch(
        f"{settings.API_V1_STR}/auth/users/usr-role-student/role",
        json={"role": "SECURITY_OFFICER"},
        headers=admin_headers,
    )
    assert promotion.status_code == 200
    assert promotion.json()["role"] == UserRole.SECURITY_OFFICER.value

    self_demotion = client.patch(
        f"{settings.API_V1_STR}/auth/users/usr-role-admin/role",
        json={"role": "STUDENT"},
        headers=admin_headers,
    )
    assert self_demotion.status_code == 400


def seed_test_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        db.query(User).delete()
        db.query(Category).delete()
        db.query(CampusLocation).delete()
        db.query(Item).delete()
        db.commit()

        user = User(
            id="usr-test-001",
            university_id="DU/R/3001/14",
            full_name="Test User",
            email="test.user@du.edu.et",
            phone="+251900000000",
            role=UserRole.STUDENT,
            telegram_chat_id="123",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        location = CampusLocation(
            id="loc-test-001",
            campus_name="Main Campus",
            block_or_facility="Central Library",
            floor_or_room="Ground Floor",
            latitude=6.4,
            longitude=38.3,
        )
        category = Category(
            id="cat-test-001",
            name="Test Category",
            description="For testing item CRUD",
            verification_attributes='["brand"]',
        )
        item = Item(
            id="itm-test-001",
            user_id=user.id,
            report_type=ItemType.LOST,
            title="Original title",
            description="Original description",
            category_id=category.id,
            location_id=location.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.OPEN,
            confidential_identifiers="secret-info",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add_all([user, location, category, item])
        db.commit()
        token = create_access_token({"sub": user.id, "role": user.role.value})
        return token, item.id
    finally:
        db.close()


def test_update_item_route_updates_owned_item():
    token, item_id = seed_test_data()

    response = client.patch(
        f"{settings.API_V1_STR}/items/{item_id}",
        json={"title": "Updated title", "description": "Updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Updated title"
    assert payload["description"] == "Updated description"


def test_delete_item_route_removes_owned_item():
    token, item_id = seed_test_data()

    response = client.delete(
        f"{settings.API_V1_STR}/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["item_id"] == item_id


def test_claim_submission_rejects_nonexistent_linked_item():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            id="usr-claimant-001",
            university_id="DU/R/5001/14",
            full_name="Claimant User",
            email="claimant.user@du.edu.et",
            phone="+251900000002",
            role=UserRole.STUDENT,
            telegram_chat_id="321",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        location = CampusLocation(
            id="loc-claim-001",
            campus_name="Main Campus",
            block_or_facility="Central Library",
            floor_or_room="Reading Hall",
            latitude=6.40,
            longitude=38.30,
        )
        category = Category(
            id="cat-claim-001",
            name="Books",
            description="Printed materials",
            verification_attributes='["title", "author"]',
        )
        found_item = Item(
            id="itm-found-claim-001",
            user_id=user.id,
            report_type=ItemType.FOUND,
            title="Found book",
            description="A found textbook",
            category_id=category.id,
            location_id=location.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.OPEN,
            confidential_identifiers="Sticker on cover",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add_all([user, location, category, found_item])
        db.commit()
        found_item_id = found_item.id
        token = create_access_token({"sub": user.id, "role": user.role.value})
    finally:
        db.close()

    response = client.post(
        f"{settings.API_V1_STR}/claims",
        json={
            "found_item_id": found_item_id,
            "lost_item_id": "itm-missing-999",
            "proof_description": "I can identify the book by the sticker.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "lost item not found" in response.json()["detail"].lower()


def test_category_lookup_and_duplicate_validation():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        admin = User(
            id="usr-admin-test",
            university_id="DU/ADM/999",
            full_name="Admin User",
            email="admin.user@du.edu.et",
            phone="+251900000001",
            role=UserRole.ADMIN,
            telegram_chat_id="222",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.commit()
        token = create_access_token({"sub": admin.id, "role": admin.role.value})
    finally:
        db.close()

    create_response = client.post(
        f"{settings.API_V1_STR}/categories",
        json={"name": "Electronics", "description": "Electronic devices"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201
    category_id = create_response.json()["id"]

    fetch_response = client.get(
        f"{settings.API_V1_STR}/categories/{category_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert fetch_response.status_code == 200
    assert fetch_response.json()["name"] == "Electronics"

    duplicate_response = client.post(
        f"{settings.API_V1_STR}/categories",
        json={"name": "Electronics", "description": "Duplicate"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"].lower()


def test_student_claim_list_respects_status_filter_for_own_claims():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            id="usr-claim-list-001",
            university_id="DU/R/7001/14",
            full_name="Claim List User",
            email="claimlist.user@du.edu.et",
            phone="+251900000005",
            role=UserRole.STUDENT,
            telegram_chat_id="101",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        location = CampusLocation(
            id="loc-claim-list-001",
            campus_name="Main Campus",
            block_or_facility="Engineering Block",
            floor_or_room="Room 101",
            latitude=6.4,
            longitude=38.3,
        )
        category = Category(
            id="cat-claim-list-001",
            name="Electronics",
            description="Electronic devices",
            verification_attributes='["brand"]',
        )
        submitted_item = Item(
            id="itm-claim-list-submitted",
            user_id=user.id,
            report_type=ItemType.FOUND,
            title="Submitted claim item",
            description="Pending claim item",
            category_id=category.id,
            location_id=location.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.OPEN,
            confidential_identifiers="tag-123",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        approved_item = Item(
            id="itm-claim-list-approved",
            user_id=user.id,
            report_type=ItemType.FOUND,
            title="Approved claim item",
            description="Approved claim item",
            category_id=category.id,
            location_id=location.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.RESOLVED,
            confidential_identifiers="tag-456",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        submitted_claim = Claim(
            id="clm-claim-list-submitted",
            found_item_id=submitted_item.id,
            claimant_id=user.id,
            lost_item_id=None,
            proof_description="I can describe the item.",
            status=ClaimStatus.SUBMITTED,
            created_at=datetime.now(timezone.utc),
        )
        approved_claim = Claim(
            id="clm-claim-list-approved",
            found_item_id=approved_item.id,
            claimant_id=user.id,
            lost_item_id=None,
            proof_description="I can prove it is mine.",
            status=ClaimStatus.APPROVED,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([user, location, category, submitted_item, approved_item, submitted_claim, approved_claim])
        db.commit()
        token = create_access_token({"sub": user.id, "role": user.role.value})
    finally:
        db.close()

    response = client.get(
        f"{settings.API_V1_STR}/claims?status_filter=APPROVED",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "clm-claim-list-approved"


def test_user_can_read_notifications_and_mark_them_as_read():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            id="usr-notify-001",
            university_id="DU/R/6001/14",
            full_name="Notification User",
            email="notify.user@du.edu.et",
            phone="+251900000003",
            role=UserRole.STUDENT,
            telegram_chat_id="456",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        notification = Notification(
            id="not-001",
            user_id=user.id,
            title="Match Alert",
            message="A possible match was found for your lost item.",
            notification_type="MATCH",
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([user, notification])
        db.commit()
        token = create_access_token({"sub": user.id, "role": user.role.value})
    finally:
        db.close()

    listing = client.get(
        f"{settings.API_V1_STR}/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    payload = listing.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Match Alert"

    update = client.patch(
        f"{settings.API_V1_STR}/notifications/{payload[0]['id']}/read",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update.status_code == 200
    assert update.json()["is_read"] is True


def test_user_can_get_unread_count_and_mark_all_notifications_read():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        user = User(
            id="usr-notify-002",
            university_id="DU/R/6002/14",
            full_name="Unread Notification User",
            email="unread.notify@du.edu.et",
            phone="+251900000004",
            role=UserRole.STUDENT,
            telegram_chat_id="789",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        unread = Notification(
            id="not-002",
            user_id=user.id,
            title="Unread alert",
            message="You have an unread notice.",
            notification_type="SYSTEM",
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        read = Notification(
            id="not-003",
            user_id=user.id,
            title="Already read",
            message="This one is already read.",
            notification_type="SYSTEM",
            is_read=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([user, unread, read])
        db.commit()
        token = create_access_token({"sub": user.id, "role": user.role.value})
    finally:
        db.close()

    unread_count = client.get(
        f"{settings.API_V1_STR}/notifications/unread-count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert unread_count.status_code == 200
    assert unread_count.json()["unread_count"] == 1

    mark_all = client.patch(
        f"{settings.API_V1_STR}/notifications/read-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mark_all.status_code == 200
    payload = mark_all.json()
    assert payload["updated_count"] == 1
    assert payload["unread_count"] == 0


def setup_privacy_test_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    sync_database_schema(engine)

    db = TestingSessionLocal()
    try:
        pw = get_password_hash("password123")
        student1 = User(
            id="usr-s1",
            university_id="DU/R/1001/14",
            full_name="Abebe Student",
            email="abebe@du.edu.et",
            role=UserRole.STUDENT,
            hashed_password=pw,
            is_active=True,
        )
        student2 = User(
            id="usr-s2",
            university_id="DU/R/1002/14",
            full_name="Tigist Student",
            email="tigist@du.edu.et",
            role=UserRole.STUDENT,
            hashed_password=pw,
            is_active=True,
        )
        student3 = User(
            id="usr-s3",
            university_id="DU/R/1003/14",
            full_name="Stranger Student",
            email="stranger@du.edu.et",
            role=UserRole.STUDENT,
            hashed_password=pw,
            is_active=True,
        )
        officer = User(
            id="usr-off1",
            university_id="DU/SEC/001",
            full_name="Officer Chala",
            email="chala@du.edu.et",
            role=UserRole.SECURITY_OFFICER,
            hashed_password=pw,
            is_active=True,
        )
        loc = CampusLocation(
            id="loc-lib",
            campus_name="Main Campus",
            block_or_facility="Library",
            floor_or_room="1st Floor",
        )
        cat = Category(
            id="cat-elec",
            name="Electronics",
            description="Laptops and devices",
        )
        lost_item = Item(
            id="itm-lost-01",
            user_id=student1.id,
            report_type=ItemType.LOST,
            title="Black HP Laptop",
            description="Lost my HP laptop in library",
            category_id=cat.id,
            location_id=loc.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.OPEN,
            confidential_identifiers="Abebe-Secret-Serial-1234",
            created_at=datetime.now(timezone.utc),
        )
        found_item = Item(
            id="itm-found-01",
            user_id=officer.id,
            report_type=ItemType.FOUND,
            title="HP Pavilion Laptop",
            description="Found black laptop in library desk 4",
            category_id=cat.id,
            location_id=loc.id,
            incident_date=datetime.now(timezone.utc),
            status=ItemStatus.OPEN,
            confidential_identifiers="Officer-Secret-Serial-1234-Sticker",
            created_at=datetime.now(timezone.utc),
        )
        match = Match(
            id="mat-01",
            lost_item_id=lost_item.id,
            found_item_id=found_item.id,
            image_score=0.0,
            text_score=0.88,
            meta_score=0.90,
            final_score=0.88,
            status=MatchStatus.SUGGESTED,
            created_at=datetime.now(timezone.utc),
        )

        db.add_all([student1, student2, student3, officer, loc, cat, lost_item, found_item, match])
        db.commit()

        token_s1 = create_access_token({"sub": student1.id, "role": student1.role.value})
        token_s2 = create_access_token({"sub": student2.id, "role": student2.role.value})
        token_s3 = create_access_token({"sub": student3.id, "role": student3.role.value})
        token_off = create_access_token({"sub": officer.id, "role": officer.role.value})

        return token_s1, token_s2, token_s3, token_off
    finally:
        db.close()


def test_student_cannot_see_confidential_identifiers_of_matched_found_item():
    token_s1, _, _, token_off = setup_privacy_test_data()

    res = client.get(
        f"{settings.API_V1_STR}/matches/my-matches",
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert res.status_code == 200
    matches = res.json()
    assert len(matches) == 1
    m = matches[0]

    assert m["lost_item"]["confidential_identifiers"] == "Abebe-Secret-Serial-1234"
    assert m["found_item"]["confidential_identifiers"] is None

    res_off = client.get(
        f"{settings.API_V1_STR}/matches/review-queue",
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert res_off.status_code == 200
    matches_off = res_off.json()
    assert len(matches_off) == 1
    m_off = matches_off[0]
    assert m_off["lost_item"]["confidential_identifiers"] == "Abebe-Secret-Serial-1234"
    assert m_off["found_item"]["confidential_identifiers"] == "Officer-Secret-Serial-1234-Sticker"


def test_match_detail_access_control():
    token_s1, _, token_s3, token_off = setup_privacy_test_data()

    res = client.get(
        f"{settings.API_V1_STR}/matches/mat-01",
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert res.status_code == 200

    res = client.get(
        f"{settings.API_V1_STR}/matches/mat-01",
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert res.status_code == 200

    res = client.get(
        f"{settings.API_V1_STR}/matches/mat-01",
        headers={"Authorization": f"Bearer {token_s3}"},
    )
    assert res.status_code == 403


def test_only_item_owner_or_staff_can_trigger_ai_matching():
    token_s1, _, token_s3, token_off = setup_privacy_test_data()

    res = client.post(
        f"{settings.API_V1_STR}/matches/trigger/itm-lost-01",
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert res.status_code == 200

    res = client.post(
        f"{settings.API_V1_STR}/matches/trigger/itm-lost-01",
        headers={"Authorization": f"Bearer {token_s3}"},
    )
    assert res.status_code == 403

    res = client.post(
        f"{settings.API_V1_STR}/matches/trigger/itm-lost-01",
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert res.status_code == 200


def test_item_deletion_succeeds_even_with_associated_matches_and_claims():
    token_s1, _, _, _ = setup_privacy_test_data()

    res = client.delete(
        f"{settings.API_V1_STR}/items/itm-lost-01",
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert res.status_code == 200
    assert res.json()["item_id"] == "itm-lost-01"

    db = TestingSessionLocal()
    try:
        assert db.query(Item).filter(Item.id == "itm-lost-01").first() is None
        assert db.query(Match).filter(Match.lost_item_id == "itm-lost-01").first() is None
    finally:
        db.close()


def test_physical_custody_handover_workflow():
    token_s1, token_s2, _, token_off = setup_privacy_test_data()

    # 1. Student 1 submits Claim A
    claim_a_res = client.post(
        f"{settings.API_V1_STR}/claims",
        json={
            "found_item_id": "itm-found-01",
            "lost_item_id": "itm-lost-01",
            "proof_description": "My laptop has an Octocat sticker and serial ending 1234.",
        },
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert claim_a_res.status_code == 201
    claim_a_id = claim_a_res.json()["id"]

    # 2. Student 2 submits Claim B (competing claim)
    claim_b_res = client.post(
        f"{settings.API_V1_STR}/claims",
        json={
            "found_item_id": "itm-found-01",
            "proof_description": "I think it is my laptop.",
        },
        headers={"Authorization": f"Bearer {token_s2}"},
    )
    assert claim_b_res.status_code == 201
    claim_b_id = claim_b_res.json()["id"]

    # 3. Officer verifies and APPROVES Claim A
    verify_res = client.patch(
        f"{settings.API_V1_STR}/claims/{claim_a_id}/verify",
        json={"status": "APPROVED", "officer_notes": "Serial number matches perfectly."},
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert verify_res.status_code == 200
    claim_a_approved = verify_res.json()
    assert claim_a_approved["status"] == "APPROVED"
    assert claim_a_approved["handover_code"] is not None
    assert claim_a_approved["handover_code"].startswith("DU-")
    handover_code = claim_a_approved["handover_code"]

    # 4. Verify competing Claim B was automatically rejected
    claim_b_fetch = client.get(
        f"{settings.API_V1_STR}/claims/{claim_b_id}",
        headers={"Authorization": f"Bearer {token_s2}"},
    )
    assert claim_b_fetch.status_code == 200
    assert claim_b_fetch.json()["status"] == "REJECTED"

    # 5. Student cannot call the officer handover endpoint
    student_attempt = client.post(
        f"{settings.API_V1_STR}/claims/{claim_a_id}/handover",
        json={"verification_code": handover_code},
        headers={"Authorization": f"Bearer {token_s1}"},
    )
    assert student_attempt.status_code == 403

    # 6. Officer supplies WRONG code
    bad_code_attempt = client.post(
        f"{settings.API_V1_STR}/claims/{claim_a_id}/handover",
        json={"verification_code": "DU-WRONG99"},
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert bad_code_attempt.status_code == 400
    assert "invalid physical handover verification code" in bad_code_attempt.json()["detail"].lower()

    # 7. Officer supplies CORRECT code -> Physical handover succeeds!
    handover_res = client.post(
        f"{settings.API_V1_STR}/claims/{claim_a_id}/handover",
        json={
            "verification_code": handover_code,
            "handover_notes": "Student verified with ID DU/R/1001/14. Physical laptop handed over.",
        },
        headers={"Authorization": f"Bearer {token_off}"},
    )
    assert handover_res.status_code == 200
    handover_payload = handover_res.json()
    assert handover_payload["status"] == "HANDED_OVER"
    assert handover_payload["handed_over_at"] is not None
    assert handover_payload["handover_officer_id"] == "usr-off1"
    assert handover_payload["handover_notes"] == "Student verified with ID DU/R/1001/14. Physical laptop handed over."

