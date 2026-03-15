# -*- coding: utf-8 -*-
"""
Mercado Pago payment integration service for Ultrafoot 26 licensing.

This service creates payment preferences and verifies payments
to deliver serial keys for game registration.

SETUP:
1. Create a Mercado Pago application at https://www.mercadopago.com.br/developers
2. Get your ACCESS_TOKEN (production) and set it below or via environment variable
3. Configure webhook URL for payment notifications
"""
from __future__ import annotations

import hashlib
import hmac
import os
import string
import time
import json
from typing import Dict, Optional

from utils.logger import get_logger

log = get_logger(__name__)

# ── Configuração ──
# Substitua pelo seu Access Token do Mercado Pago (produção)
MP_ACCESS_TOKEN = os.environ.get(
    "MP_ACCESS_TOKEN",
    "APP_USR-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
)

# URLs de callback após pagamento
CALLBACK_BASE_URL = os.environ.get(
    "CALLBACK_BASE_URL",
    "https://seu-servidor.com"
)

# Produto
PRODUCT_TITLE = "Ultrafoot 26 — Registro Completo"
PRODUCT_PRICE = 29.90
PRODUCT_CURRENCY = "BRL"

# Serial generation
_SERIAL_SALT = "ULTRAFOOT_OFFLINE_2026"
_ALPHABET = string.digits + string.ascii_uppercase


def _base36(num: int) -> str:
    if num <= 0:
        return "0"
    out = []
    while num:
        num, rem = divmod(num, 36)
        out.append(_ALPHABET[rem])
    return "".join(reversed(out))


def _generate_serial_for_payment(payment_id: str, email: str) -> str:
    """Generate a valid UF26 serial key tied to a specific payment."""
    seed = f"UF26-{payment_id}-{email}-{_SERIAL_SALT}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()

    # Build body: UF26 + segments from hash
    body = "UF26" + digest[:12].upper()

    # Compute checksum
    check_digest = hashlib.sha256(
        (body + _SERIAL_SALT).encode("utf-8")
    ).hexdigest().upper()
    checksum = _base36(int(check_digest[:10], 16))[:6].rjust(6, "0")

    raw = body + checksum
    # Format as UF26-XXXX-XXXX-XXXX-XXXX
    parts = [raw[i:i+4] for i in range(0, len(raw), 4)]
    return "-".join(parts)


class PaymentService:
    """Handles Mercado Pago payment creation and verification."""

    def __init__(self) -> None:
        self._payments_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "payment_records.json"
        )
        self._records = self._load_records()

    def _load_records(self) -> Dict:
        if os.path.isfile(self._payments_file):
            try:
                with open(self._payments_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"payments": {}}

    def _save_records(self) -> None:
        tmp = self._payments_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._payments_file)

    def criar_preferencia(self, nome: str, email: str) -> Dict:
        """
        Create a Mercado Pago payment preference.
        Returns dict with 'init_point' (checkout URL) or error.
        """
        try:
            import mercadopago
        except ImportError:
            log.error("mercadopago SDK não instalado. Execute: pip install mercadopago")
            return {"error": "SDK mercadopago não disponível"}

        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

        preference_data = {
            "items": [
                {
                    "title": PRODUCT_TITLE,
                    "quantity": 1,
                    "unit_price": PRODUCT_PRICE,
                    "currency_id": PRODUCT_CURRENCY,
                    "description": "Licença permanente do Ultrafoot 26 com todos os recursos",
                }
            ],
            "payer": {
                "name": nome,
                "email": email,
            },
            "back_urls": {
                "success": f"{CALLBACK_BASE_URL}/landing/?status=approved",
                "failure": f"{CALLBACK_BASE_URL}/landing/?status=failure",
                "pending": f"{CALLBACK_BASE_URL}/landing/?status=pending",
            },
            "auto_return": "approved",
            "payment_methods": {
                "excluded_payment_types": [],
                "installments": 1,
            },
            "statement_descriptor": "ULTRAFOOT26",
            "external_reference": f"uf26_{email}_{int(time.time())}",
        }

        result = sdk.preference().create(preference_data)
        response = result.get("response", {})

        if response.get("init_point"):
            # Store pending payment
            self._records["payments"][response["id"]] = {
                "nome": nome,
                "email": email,
                "status": "pending",
                "created_at": int(time.time()),
                "preference_id": response["id"],
            }
            self._save_records()

            return {
                "init_point": response["init_point"],
                "preference_id": response["id"],
            }

        log.error("Erro ao criar preferência MP: %s", result)
        return {"error": "Falha ao criar preferência de pagamento"}

    def verificar_pagamento(self, payment_id: str) -> Dict:
        """
        Verify a payment and return the serial key if approved.
        """
        try:
            import mercadopago
        except ImportError:
            return {"error": "SDK mercadopago não disponível"}

        sdk = mercadopago.SDK(MP_ACCESS_TOKEN)
        result = sdk.payment().get(payment_id)
        payment = result.get("response", {})

        if payment.get("status") == "approved":
            email = payment.get("payer", {}).get("email", "unknown")
            serial = _generate_serial_for_payment(payment_id, email)

            # Store approved payment with serial
            self._records["payments"][payment_id] = {
                "email": email,
                "status": "approved",
                "serial": serial,
                "approved_at": int(time.time()),
            }
            self._save_records()

            return {
                "status": "approved",
                "serial": serial,
                "email": email,
            }

        return {
            "status": payment.get("status", "unknown"),
            "serial": None,
        }

    def webhook_notification(self, data: Dict) -> Dict:
        """
        Handle Mercado Pago webhook notifications.
        Called when MP sends IPN about payment status changes.
        """
        topic = data.get("type", data.get("topic", ""))
        resource_id = data.get("data", {}).get("id", data.get("id", ""))

        if topic == "payment" and resource_id:
            return self.verificar_pagamento(str(resource_id))

        return {"status": "ignored"}
