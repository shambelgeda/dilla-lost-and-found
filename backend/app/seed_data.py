import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.location import CampusLocation
from app.models.category import Category
from app.models.item import Item, ItemType, ItemStatus, ItemImage
from app.services.auth import get_password_hash
from app.services.ai_engine import process_and_store_embedding, run_matching_engine_for_item

def seed_database(db: Session):
    # Only seed if database is empty of users
    if db.query(User).count() > 0:
        return

    print("🌱 Seeding initial Dilla University database records...")

    # 1. Seed Users
    default_pw = get_password_hash("password123")
    
    users = [
        User(
            id="usr-student-abebe",
            university_id="DU/R/1042/14",
            full_name="Abebe Kebede",
            email="abebe.kebede@du.edu.et",
            phone="+251911223344",
            role=UserRole.STUDENT,
            telegram_chat_id="123456789",
            hashed_password=default_pw,
            is_active=True
        ),
        User(
            id="usr-student-tigist",
            university_id="DU/R/2105/14",
            full_name="Tigist Haile",
            email="tigist.haile@du.edu.et",
            phone="+251922334455",
            role=UserRole.STUDENT,
            telegram_chat_id="987654321",
            hashed_password=default_pw,
            is_active=True
        ),
        User(
            id="usr-officer-chala",
            university_id="DU/SEC/008",
            full_name="Officer Chala Bekele",
            email="security.chala@du.edu.et",
            phone="+251933445566",
            role=UserRole.SECURITY_OFFICER,
            telegram_chat_id="555666777",
            hashed_password=default_pw,
            is_active=True
        ),
        User(
            id="usr-admin-solomon",
            university_id="DU/ADM/001",
            full_name="Solomon Tadesse (System Admin)",
            email="admin.solomon@du.edu.et",
            phone="+251944556677",
            role=UserRole.ADMIN,
            hashed_password=default_pw,
            is_active=True
        )
    ]
    db.add_all(users)
    db.commit()

    # 2. Seed Campus Locations
    locations = [
        CampusLocation(
            id="loc-odayaa-lab204",
            campus_name="Odayaa Campus (Tech / IoT)",
            block_or_facility="Block 204 - Software Engineering Lab",
            floor_or_room="2nd Floor, Room 204",
            latitude=6.4180,
            longitude=38.3120
        ),
        CampusLocation(
            id="loc-main-library",
            campus_name="Main Campus",
            block_or_facility="Central Library",
            floor_or_room="Ground Floor Main Reading Hall",
            latitude=6.4150,
            longitude=38.3090
        ),
        CampusLocation(
            id="loc-main-cafe",
            campus_name="Main Campus",
            block_or_facility="Student Cafeteria",
            floor_or_room="Dining Hall 1 Entrance",
            latitude=6.4140,
            longitude=38.3080
        ),
        CampusLocation(
            id="loc-health-library",
            campus_name="Health Science Campus",
            block_or_facility="Medical Library",
            floor_or_room="1st Floor Study Cubicles",
            latitude=6.4195,
            longitude=38.3150
        ),
        CampusLocation(
            id="loc-main-dorm14",
            campus_name="Main Campus",
            block_or_facility="Block 14 Male Dormitory",
            floor_or_room="Common Room",
            latitude=6.4125,
            longitude=38.3075
        )
    ]
    db.add_all(locations)
    db.commit()

    # 3. Seed Categories
    categories = [
        Category(
            id="cat-electronics",
            name="Laptops & Computers",
            description="Laptops, netbooks, chargers, and computing accessories",
            verification_attributes='["brand", "serial_number", "desktop_wallpaper", "installed_stickers"]'
        ),
        Category(
            id="cat-phones",
            name="Mobile Phones & Tablets",
            description="Smartphones, feature phones, tablets, earbuds",
            verification_attributes='["phone_model", "screen_lock_type", "phone_case_color", "carrier_sim"]'
        ),
        Category(
            id="cat-ids",
            name="Student IDs & Official Documents",
            description="University ID cards, bank passbooks, passports, national IDs",
            verification_attributes='["full_name_on_id", "id_number", "department_name"]'
        ),
        Category(
            id="cat-bags",
            name="Bags & Backpacks",
            description="School bags, laptop bags, handbags, wallets",
            verification_attributes='["bag_brand", "internal_contents", "zipper_type"]'
        ),
        Category(
            id="cat-keys",
            name="Keys & Locks",
            description="Dormitory keys, padlock keys, vehicle keys",
            verification_attributes='["number_of_keys", "keychain_description"]'
        )
    ]
    db.add_all(categories)
    db.commit()

    # 4. Seed Realistic Sample Items (Lost and Found pairs to trigger AI matching)
    now = datetime.now(timezone.utc)

    # Pair A: HP Laptop in Odayaa Campus Lab 204
    lost_laptop = Item(
        id="itm-lost-hp-laptop",
        user_id="usr-student-abebe",
        report_type=ItemType.LOST,
        title="Black HP Pavilion 15 Laptop with GitHub sticker",
        description="Lost my black HP Pavilion 15-inch laptop during Software Engineering lab. Has a dark grey keyboard cover and an Octocat sticker on top. ጥቁር HP ላፕቶፕ ኮምፒውተር በሶፍትዌር ላብ ተረስቶብኛል።",
        category_id="cat-electronics",
        location_id="loc-odayaa-lab204",
        incident_date=now - timedelta(days=2),
        status=ItemStatus.OPEN,
        confidential_identifiers="Serial ends with 842109X; Ubuntu 22.04 LTS boot wallpaper",
        created_at=now - timedelta(days=2)
    )

    found_laptop = Item(
        id="itm-found-hp-laptop",
        user_id="usr-officer-chala",
        report_type=ItemType.FOUND,
        title="HP Laptop found in Software Lab desk 14",
        description="Found black/dark grey HP laptop left behind on computer lab desk. Kept safely at Security Office. ላፕቶፕ በላብራቶሪ ተገኝቶ ተይዟል።",
        category_id="cat-electronics",
        location_id="loc-odayaa-lab204",
        incident_date=now - timedelta(days=1),
        status=ItemStatus.OPEN,
        confidential_identifiers="Serial Number: HP-CNU842109X; Octocat sticker near trackpad",
        created_at=now - timedelta(days=1)
    )

    # Pair B: Samsung Phone in Central Library
    lost_phone = Item(
        id="itm-lost-samsung-phone",
        user_id="usr-student-tigist",
        report_type=ItemType.LOST,
        title="Samsung Galaxy A53 Smartphone (Light Blue)",
        description="Lost light blue Samsung Galaxy phone with transparent silicon case at the Central Library reading table. ሰማያዊ ሳምሰንግ ሞባይል ስልክ ቤተመጻሕፍት ውስጥ ጠፍቶብኛል።",
        category_id="cat-phones",
        location_id="loc-main-library",
        incident_date=now - timedelta(days=3),
        status=ItemStatus.OPEN,
        confidential_identifiers="Lock screen wallpaper is sunset at Lake Chamo; 6-digit PIN",
        created_at=now - timedelta(days=3)
    )

    found_phone = Item(
        id="itm-found-samsung-phone",
        user_id="usr-officer-chala",
        report_type=ItemType.FOUND,
        title="Blue Samsung Android Phone in clear cover",
        description="A student handed in a blue Samsung touchscreen smartphone found at the Main Campus Library first floor. ስልክ በቤተ-መጽሐፍት ተገኝቷል።",
        category_id="cat-phones",
        location_id="loc-main-library",
        incident_date=now - timedelta(days=2),
        status=ItemStatus.OPEN,
        confidential_identifiers="SIM 1: Ethio Telecom, Lake wallpaper on lockscreen",
        created_at=now - timedelta(days=2)
    )

    # Item C: Student ID Card
    lost_id_card = Item(
        id="itm-lost-id-tigist",
        user_id="usr-student-tigist",
        report_type=ItemType.LOST,
        title="Dilla University Student ID Card - Tigist Haile",
        description="Lost my official student ID card near the student cafeteria. Department of Computer Science, 3rd year. የተማሪ መታወቂያ ካርድ በካፍቴሪያ አካባቢ ጠፍቷል።",
        category_id="cat-ids",
        location_id="loc-main-cafe",
        incident_date=now - timedelta(days=1),
        status=ItemStatus.OPEN,
        confidential_identifiers="ID: DU/R/2105/14, Photo has green background",
        created_at=now - timedelta(days=1)
    )

    items_to_seed = [lost_laptop, found_laptop, lost_phone, found_phone, lost_id_card]
    db.add_all(items_to_seed)
    db.commit()

    # Generate Embeddings and Trigger AI Matching Engine
    for itm in items_to_seed:
        db.refresh(itm)
        process_and_store_embedding(itm, db)
        run_matching_engine_for_item(itm, db)

    print("✅ Database successfully seeded with Dilla University sample dataset and AI matches calculated!")
