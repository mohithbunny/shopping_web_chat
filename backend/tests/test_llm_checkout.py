import unittest
from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.core.database import Base, utcnow
from app.models import CartItem, Order, PendingCheckout, Product, User
from app.services import llm_service


class CheckoutConversationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(name="Test Customer", email="test@example.com", password_hash="hash")
        product = Product(name="Notebook", category="Stationery", price=299, stock=5)
        self.db.add_all([self.user, product])
        self.db.commit()
        self.db.add(CartItem(user_id=self.user.id, product_id=product.id, quantity=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_confirms_clear_phrases_from_conversation(self):
        for message in (
            "please place order",
            "yes place order",
            "yes please with shipping address Shipping to: my home",
        ):
            with self.subTest(message=message):
                self.assertTrue(llm_service._is_explicit_confirmation(message))

    def test_does_not_confirm_negated_or_inquisitive_messages(self):
        for message in ("no, don't place the order", "how do I place an order?"):
            with self.subTest(message=message):
                self.assertFalse(llm_service._is_explicit_confirmation(message))

    def test_confirmation_works_after_pending_checkout_is_loaded_in_another_session(self):
        ctx = llm_service.Ctx(db=self.db, user=self.user)
        llm_service.t_prepare_checkout(ctx, "Street 1, Hyderabad")
        self.assertIsNotNone(self.db.get(PendingCheckout, self.user.id))

        with Session(self.engine) as confirmation_db:
            result = llm_service.llm_invoke(
                "please place order", [], confirmation_db, confirmation_db.get(User, self.user.id)
            )

        self.assertIn("placed successfully", result["output"])
        with Session(self.engine) as verify_db:
            self.assertEqual(len(list(verify_db.scalars(select(Order)).all())), 1)
            self.assertIsNone(verify_db.get(PendingCheckout, self.user.id))
            self.assertEqual(verify_db.scalars(select(CartItem)).all(), [])

    def test_expired_confirmation_is_cleared(self):
        self.db.add(PendingCheckout(
            user_id=self.user.id,
            shipping_address="Street 1, Hyderabad",
            expires_at=utcnow() - timedelta(seconds=1),
        ))
        self.db.commit()

        result = llm_service.llm_invoke("yes", [], self.db, self.user)

        self.assertIn("expired", result["output"])
        self.assertIsNone(self.db.get(PendingCheckout, self.user.id))


if __name__ == "__main__":
    unittest.main()
