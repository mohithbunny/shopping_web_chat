"""Create the admin account and (optionally) demo data.

    python seed.py              # admin + demo products, customers and 4 weeks of orders
    python seed.py --no-demo    # admin account only
    python seed.py --reset      # wipe the database first, then seed
"""
import argparse
import random
from datetime import timedelta

from sqlalchemy import select

from app import models  # noqa: F401
from app.core.database import Base, SessionLocal, engine, utcnow
from app.core.security import hash_password
from app.models import Product, User
from app.services import order_service

ADMIN = ("Store Admin", "admin@shop.com", "admin123")
DEMO_CUSTOMER = ("Demo Customer", "customer@shop.com", "customer123")

PRODUCTS = [
    # name, category, price, stock, description
    ("Cast iron skillet, 26 cm", "Kitchen", 1499, 60, "Pre-seasoned skillet that goes from stovetop to oven."),
    ("Steel water bottle, 1 L", "Kitchen", 649, 120, "Double-walled; keeps drinks cold for 24 hours."),
    ("Ceramic mug set of 4", "Kitchen", 899, 70, "Stoneware mugs, 350 ml each, dishwasher safe."),
    ("Bamboo cutting board", "Kitchen", 549, 80, "Large board with a juice groove on one side."),
    ("Wireless earbuds", "Electronics", 2499, 50, "Up to 30 hours with the case. Fits snugly for workouts."),
    ("USB-C charger, 30 W", "Electronics", 999, 90, "Fast-charges phones and small laptops."),
    ("Bluetooth speaker", "Electronics", 1899, 45, "Splash resistant, 12 hours of playback."),
    ("Power bank, 10,000 mAh", "Electronics", 1299, 75, "Slim enough for a pocket; charges two devices at once."),
    ("Cotton bedsheet set", "Home", 1199, 55, "Queen sheet with two pillow covers, 300 thread count."),
    ("Scented soy candle", "Home", 399, 100, "Sandalwood and vanilla, about 40 hours of burn time."),
    ("Ceramic plant pot", "Home", 599, 65, "15 cm pot with drainage hole and saucer."),
    ("Knit throw blanket", "Home", 1399, 40, "Soft acrylic knit, 130 x 170 cm."),
    ("Organic cotton T-shirt", "Clothing", 599, 150, "Regular fit crew neck in six colours."),
    ("Running shorts", "Clothing", 799, 90, "Lightweight with a zip pocket."),
    ("Canvas sneakers", "Clothing", 1999, 4, "Classic low-tops with a cushioned insole."),
    ("Wool socks, 3 pairs", "Clothing", 499, 110, "Merino blend, warm without overheating."),
    ("Dotted notebook, A5", "Stationery", 299, 140, "160 pages of 100 gsm paper that resists bleed-through."),
    ("Gel pen set of 10", "Stationery", 249, 130, "Smooth 0.5 mm tips in assorted colours."),
    ("Desk planner 2027", "Stationery", 449, 3, "Week-to-view layout with monthly goals pages."),
    ("Gentle face wash", "Personal care", 349, 95, "Soap-free cleanser for daily use."),
    ("Bamboo toothbrushes, 4", "Personal care", 199, 160, "Soft bristles with compostable handles."),
    ("Sunscreen SPF 50", "Personal care", 549, 85, "Light, non-greasy, no white cast."),
]

CUSTOMERS = [
    "Aarav Sharma", "Priya Nair", "Daniel Brooks", "Ananya Iyer", "Vikram Reddy",
    "Sofia Martins", "Arjun Mehta", "Kavya Rao", "Lena Fischer", "Omar Haddad",
]

ADDRESSES = [
    "12 Lake View Road, Apt 4B", "221 Park Street, 2nd Floor", "7 Market Lane, Near City Mall",
    "45 Hill Crest Avenue", "89 Riverside Drive, Block C",
]


def seed(demo: bool, reset: bool) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Database already has data. Run with --reset to start fresh.")
            return

        db.add(User(name=ADMIN[0], email=ADMIN[1], password_hash=hash_password(ADMIN[2]), role="admin"))
        db.commit()
        print(f"Admin created: {ADMIN[1]} / {ADMIN[2]}")
        if not demo:
            return

        rng = random.Random(42)
        now = utcnow()

        products = []
        for name, cat, price, stock, desc in PRODUCTS:
            p = Product(name=name, category=cat, price=price, stock=stock, description=desc,
                        created_at=now - timedelta(days=40))
            db.add(p)
            products.append(p)

        customers = [User(name=DEMO_CUSTOMER[0], email=DEMO_CUSTOMER[1],
                          password_hash=hash_password(DEMO_CUSTOMER[2]),
                          created_at=now - timedelta(days=35))]
        pw = hash_password("password123")
        for i, name in enumerate(CUSTOMERS):
            email = name.lower().replace(" ", ".") + "@example.org"
            # Spread sign-ups over the last 5 weeks so "new customers" varies by week.
            joined = now - timedelta(days=rng.randint(1, 35), hours=rng.randint(0, 23))
            customers.append(User(name=name, email=email, password_hash=pw, created_at=joined))
        db.add_all(customers)
        db.commit()

        # Popular items get picked more often, so the charts have a shape.
        weights = [rng.uniform(0.5, 3) for _ in products]
        weights[14] = weights[18] = 0.15  # keep the low-stock items rare
        order_count = 0
        for _ in range(85):
            customer = rng.choice(customers)
            days_since_join = max((now - customer.created_at).days, 0)
            when = now - timedelta(days=rng.randint(0, min(27, days_since_join)),
                                   hours=rng.randint(0, 20), minutes=rng.randint(0, 59))
            if when < customer.created_at:
                when = customer.created_at + timedelta(hours=1)
            picks = set(rng.choices(range(len(products)), weights=weights, k=rng.randint(1, 3)))
            lines = [(products[i].id, rng.randint(1, 2)) for i in picks]
            try:
                order = order_service.create_order(db, customer.id, lines, rng.choice(ADDRESSES))
            except Exception:
                db.rollback()
                continue  # skip if a low-stock item ran out
            age = (now - when).days
            order.status = ("delivered" if age > 7 else "shipped" if age > 3
                            else "processing" if age > 1 else "placed")
            order.created_at = order.updated_at = when
            if rng.random() < 0.06:
                order_service.update_order_status(db, order.id, "cancelled")
            db.commit()
            order_count += 1

        print(f"Demo data: {len(products)} products, {len(customers)} customers, {order_count} orders")
        print(f"Demo customer: {DEMO_CUSTOMER[1]} / {DEMO_CUSTOMER[2]}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-demo", action="store_true", help="only create the admin account")
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    args = parser.parse_args()
    seed(demo=not args.no_demo, reset=args.reset)
