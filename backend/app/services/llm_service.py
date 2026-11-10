import json
import os
import re
from dataclasses import dataclass
from datetime import timedelta

from groq import Groq
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models import PendingCheckout
from app.services import cart_service, order_service, product_service  # ADAPT
from app.services.errors import ServiceError

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TOOL_ROUNDS = 6
CHECKOUT_CONFIRM_TTL = 300  # seconds


@dataclass
class Ctx:
    db: Session
    user: object | None
    prepared_now: bool = False   # checkout was prepared during THIS request
    cart_changed: bool = False   # lets the frontend refresh its cart UI


# ---------- serializers (ADAPT field names to your models) ----------

def _product_dict(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "price": float(p.price),
        "stock": p.stock,
        "description": getattr(p, "description", None),
        "category": getattr(p, "category", None),
    }


def _cart_dict(cart) -> dict:
    items = []
    total = 0.0
    for it in cart.get("items", []):
        product = it["product"]
        quantity = int(it.get("quantity", 0))
        line = float(it.get("line_total", product.price * quantity))
        total += line
        items.append({
            "product_id": product.id,
            "name": product.name,
            "unit_price": float(product.price),
            "quantity": quantity,
            "line_total": round(line, 2),
        })
    return {
        "items": items,
        "item_count": int(cart.get("total_items", len(items))),
        "total": round(float(cart.get("total_amount", total)), 2),
    }


def _qty(value, default=1) -> int:
    try:
        return max(0, min(int(value), 20))
    except (TypeError, ValueError):
        return default


def _clear_pending_checkout(ctx: Ctx) -> None:
    pending = ctx.db.get(PendingCheckout, ctx.user.id)
    if pending:
        ctx.db.delete(pending)
        ctx.db.commit()


# ---------- tool handlers: (ctx, **args) -> dict ----------

def t_search_products(ctx: Ctx, query: str = "", limit: int = 5):
    limit = max(1, min(int(limit or 5), 10))
    items, _ = product_service.list_products(
        ctx.db, search=query or None, in_stock_only=True, sort="newest", limit=limit,
    )  # ADAPT if your signature differs
    return {"count": len(items), "products": [_product_dict(p) for p in items]}


def t_get_product_details(ctx: Ctx, product_id: int):
    p = product_service.get_product(ctx.db, int(product_id))   # ADAPT
    return _product_dict(p)


def t_view_cart(ctx: Ctx):
    return _cart_dict(cart_service.get_cart(ctx.db, ctx.user.id))


def t_add_to_cart(ctx: Ctx, product_id: int, quantity: int = 1):
    qty = max(1, _qty(quantity))
    cart_service.add_to_cart(ctx.db, ctx.user.id, int(product_id), qty)
    _clear_pending_checkout(ctx)
    ctx.cart_changed = True
    return _cart_dict(cart_service.get_cart(ctx.db, ctx.user.id))


def t_update_cart_item(ctx: Ctx, product_id: int, quantity: int):
    """Sets the quantity to an absolute value. 0 removes the item."""
    qty = _qty(quantity, default=-1)
    if qty < 0:
        return {"error": "Invalid quantity"}
    if qty == 0:
        cart_service.remove_from_cart(ctx.db, ctx.user.id, int(product_id))
    else:
        cart_service.update_cart_item(ctx.db, ctx.user.id, int(product_id), qty)
    _clear_pending_checkout(ctx)
    ctx.cart_changed = True
    return _cart_dict(cart_service.get_cart(ctx.db, ctx.user.id))


def t_remove_from_cart(ctx: Ctx, product_id: int):
    cart_service.remove_from_cart(ctx.db, ctx.user.id, int(product_id))
    _clear_pending_checkout(ctx)
    ctx.cart_changed = True
    return _cart_dict(cart_service.get_cart(ctx.db, ctx.user.id))


def t_prepare_checkout(ctx: Ctx, shipping_address: str = ""):
    cart = _cart_dict(cart_service.get_cart(ctx.db, ctx.user.id))
    if not cart["items"]:
        return {"error": "The cart is empty."}
    address = shipping_address.strip()
    if len(address) < 5:
        return {
            "needs_shipping_address": True,
            "message": "Ask the customer for their shipping address before preparing checkout.",
        }
    pending = ctx.db.get(PendingCheckout, ctx.user.id)
    if pending:
        pending.shipping_address = address
        pending.expires_at = utcnow() + timedelta(seconds=CHECKOUT_CONFIRM_TTL)
    else:
        ctx.db.add(PendingCheckout(
            user_id=ctx.user.id,
            shipping_address=address,
            expires_at=utcnow() + timedelta(seconds=CHECKOUT_CONFIRM_TTL),
        ))
    ctx.db.commit()
    ctx.prepared_now = True
    return {
        "cart": cart,
        "next_step": "Show the user this summary and ask them to confirm. "
                     "Do NOT call confirm_checkout until the user replies in their next message.",
    }


def t_confirm_checkout(ctx: Ctx):
    pending = ctx.db.get(PendingCheckout, ctx.user.id)
    # Must have been prepared in an EARLIER request, so the model can't
    # prepare + confirm in the same turn without the user saying yes.
    if ctx.prepared_now or not pending or pending.expires_at <= utcnow():
        _clear_pending_checkout(ctx)
        return {"error": "No pending checkout. Call prepare_checkout first and get the user's confirmation."}
    order = order_service.checkout_cart(ctx.db, ctx.user.id, pending.shipping_address)
    _clear_pending_checkout(ctx)
    ctx.cart_changed = True
    return {
        "status": "order_placed",
        "order_id": getattr(order, "id", None),
        "total": float(getattr(order, "total_amount", 0) or 0),
    }


# ---------- tool registry: name -> (handler, needs_login, schema) ----------

def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []},
    }}

_PID = {"product_id": {"type": "integer", "description": "Product id from a previous tool result"}}

REGISTRY = {
    "search_products": (t_search_products, False, _fn(
        "search_products", "Search in-stock products by keyword. Empty query lists newest products.",
        {"query": {"type": "string"}, "limit": {"type": "integer"}})),
    "get_product_details": (t_get_product_details, False, _fn(
        "get_product_details", "Get full details of one product by id.", _PID, ["product_id"])),
    "view_cart": (t_view_cart, True, _fn(
        "view_cart", "Show the logged-in user's cart with totals.")),
    "add_to_cart": (t_add_to_cart, True, _fn(
        "add_to_cart", "Add a product to the user's cart.",
        {**_PID, "quantity": {"type": "integer", "description": "Default 1"}}, ["product_id"])),
    "update_cart_item": (t_update_cart_item, True, _fn(
        "update_cart_item", "Set the quantity of a cart item. Use 0 to remove it.",
        {**_PID, "quantity": {"type": "integer"}}, ["product_id", "quantity"])),
    "remove_from_cart": (t_remove_from_cart, True, _fn(
        "remove_from_cart", "Remove a product from the cart.", _PID, ["product_id"])),
    "prepare_checkout": (t_prepare_checkout, True, _fn(
        "prepare_checkout", "Prepare checkout after collecting the customer's shipping address. Returns the order summary to show the customer; does NOT place the order.",
        {"shipping_address": {"type": "string", "description": "Shipping address explicitly provided by the customer"}})),
    "confirm_checkout": (t_confirm_checkout, True, _fn(
        "confirm_checkout", "Step 2: place the order. Only call after the user explicitly confirmed in their latest message.")),
}


def _tools_for(user) -> list[dict]:
    return [schema for _, needs_login, schema in REGISTRY.values() if user or not needs_login]


def _system_prompt(user) -> str:
    base = (
        "You are the shopping assistant for Haul Shop. Use the tools to get real data; "
        "never invent products, prices, stock or order details. "
        "Always use product ids returned by tools, never guess them. "
        "If several products match a request, ask the user which one they mean. "
        "After changing the cart, tell the user the new cart contents/total. "
        "For checkout, first collect the customer's shipping address. Then call prepare_checkout "
        "with that exact address, show the summary, and ask the user to confirm. "
        "Only call confirm_checkout after they clearly say yes in a later message. "
        "Never invent or substitute a shipping address. Keep replies short and friendly."
    )
    if user:
        name = getattr(user, "name", None) or getattr(user, "email", "the customer")
        return base + f" The user is logged in as {name}."
    return base + (" The user is NOT logged in: you can search and show products, but for cart "
                   "or checkout ask them to log in first.")


# ---------- LLM plumbing ----------

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=key)
    return _client


def _is_explicit_confirmation(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.strip().lower()).rstrip("!.")
    if re.search(r"\b(?:don't|do not|not)\s+(?:place|submit|confirm|proceed)\b", normalized):
        return False
    if re.match(r"^(?:yes|yeah|yep|sure|confirmed?)(?:\b|[,!])", normalized):
        return True
    if re.match(r"^(?:please\s+)?(?:place|submit)\s+(?:the\s+)?order\b", normalized):
        return True
    return normalized in {"go ahead", "do it", "please proceed", "proceed"}


def _is_explicit_cancellation(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.strip().lower()).rstrip("!.")
    return normalized in {"no", "no thanks", "no thank you", "cancel", "cancel it", "don't"} or bool(
        re.match(
            r"^(?:no\b|please cancel\b|cancel\b|don't place\b|do not place\b|yes[, ]+(?:please[, ]+)?cancel\b)",
            normalized,
        )
    )


def _run_tool(ctx: Ctx, name: str, raw_args: str) -> str:
    entry = REGISTRY.get(name)
    if not entry:
        return json.dumps({"error": f"Unknown tool {name}"})
    handler, needs_login, _ = entry
    if needs_login and ctx.user is None:
        return json.dumps({"error": "User must log in first."})
    try:
        args = json.loads(raw_args or "{}")
        return json.dumps(handler(ctx, **args), default=str)
    except ServiceError as e:            # business errors: out of stock, not found...
        return json.dumps({"error": e.message})
    except TypeError:
        return json.dumps({"error": "Invalid arguments"})
    except Exception as e:
        print("Tool error:", name, repr(e))
        return json.dumps({"error": "Tool failed"})


def llm_invoke(message: str, history: list[dict], db: Session, user) -> dict:
    ctx = Ctx(db=db, user=user)
    if user:
        pending = db.get(PendingCheckout, user.id)
        if pending and pending.expires_at <= utcnow():
            _clear_pending_checkout(ctx)
            return {
                "output": "That checkout confirmation expired. Please ask me to check out again.",
                "cart_changed": False,
            }
        if pending and _is_explicit_cancellation(message):
            _clear_pending_checkout(ctx)
            return {"output": "Checkout cancelled. Your cart has not been changed.", "cart_changed": False}
        if pending and _is_explicit_confirmation(message):
            try:
                order = t_confirm_checkout(ctx)
            except ServiceError as exc:
                return {"output": exc.message, "cart_changed": False}
            return {
                "output": f"Order #{order['order_id']} placed successfully. Total: {order['total']:.2f}.",
                "cart_changed": ctx.cart_changed,
            }

    client = _get_client()

    messages = [{"role": "system", "content": _system_prompt(user)}]
    # Only user/assistant text from the client; never trust system/tool roles.
    for h in history[-10:]:
        if h["role"] in ("user", "assistant") and isinstance(h["content"], str):
            messages.append({"role": h["role"], "content": h["content"][:2000]})
    messages.append({"role": "user", "content": message})

    tools = _tools_for(user)

    for _ in range(MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools,
            tool_choice="auto", temperature=0.2, max_tokens=1500,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"output": msg.content or "", "cart_changed": ctx.cart_changed}

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": _run_tool(ctx, tc.function.name, tc.function.arguments),
            })

    return {"output": "Sorry, I couldn't complete that. Please try again.",
            "cart_changed": ctx.cart_changed}