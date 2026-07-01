from typing import Any
import base64
import json
from datetime import datetime, timezone

import httpx

PRODUCT_GROUPS = [
    "vegetableoil",
    "bio",
    "tobacco",
    "alcohol",
    "beer",
    "pharma",
    "water",
    "medicals",
    "appliances",
    "antiseptic",
    "fertilizers",
]


class AslApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AslClient:
    def __init__(
        self,
        base_url: str,
        api_key_header: str,
        api_key_prefix: str,
        check_path: str,
        card_path: str,
        aggregation_path: str,
        timeout: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_header = api_key_header
        self.api_key_prefix = api_key_prefix.strip()
        self.check_path = check_path
        self.card_path = card_path
        self.aggregation_path = aggregation_path
        self.timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        api_key: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        authorization_value = (
            f"{self.api_key_prefix} {api_key}" if self.api_key_prefix else api_key
        )
        headers = {
            self.api_key_header: authorization_value,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.request(
                    method, path, headers=headers, json=payload, params=params
                )
        except httpx.RequestError as exc:
            raise AslApiError(f"Asl Belgisi serveriga ulanib bo'lmadi: {exc}") from exc

        if response.is_error:
            detail = response.text[:700]
            raise AslApiError(
                f"API xatosi ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if not response.content:
            return {"ok": True}
        try:
            return response.json()
        except ValueError:
            return {"ok": True, "response": response.text[:700]}

    async def check_api_key(self, api_key: str) -> dict[str, Any]:
        return await self._request("GET", self.check_path, api_key)

    async def resolve_category(self, api_key: str, tnved: str) -> dict[str, str]:
        matches: dict[str, dict[str, str]] = {}
        for product_group in PRODUCT_GROUPS:
            try:
                result = await self._request(
                    "GET",
                    "/public/api/v1/product-registry/product",
                    api_key,
                    params={"productGroup": product_group, "tnved": tnved},
                )
            except AslApiError as exc:
                if exc.status_code in {400, 403, 404}:
                    continue
                raise
            products = result.get("products", []) if isinstance(result, dict) else result
            for product in products if isinstance(products, list) else []:
                category = product.get("productCategory") or {}
                category_code = category.get("code") or category.get("value")
                if category_code:
                    names = category.get("name") or {}
                    matches[category_code] = {
                        "productGroup": product_group,
                        "categoryCode": category_code,
                        "categoryName": names.get("uz")
                        or names.get("ru")
                        or names.get("en")
                        or category_code,
                    }

        if not matches:
            raise AslApiError(f"TNVED {tnved} uchun kategoriya topilmadi.")
        if len(matches) > 1:
            category_names = ", ".join(item["categoryName"] for item in matches.values())
            raise AslApiError(
                f"TNVED {tnved} bir nechta kategoriyaga mos keldi: {category_names}"
            )
        return next(iter(matches.values()))

    async def create_card(
        self,
        api_key: str,
        gtin: str,
        tnved: str,
        product_group: str,
        category_code: str,
    ) -> dict[str, Any]:
        if "replace-with-" in self.card_path:
            raise AslApiError(
                "Kartochka yaratish API endpointi sozlanmagan. "
                "xTrace ochiq API hujjatida yangi mahsulot kartochkasini yaratish yoki "
                "moderatsiyaga yuborish POST metodi mavjud emas. Bu amal hozircha "
                "xTrace shaxsiy kabinetidagi «Mahsulot tavsiflari» bo'limida bajariladi."
            )
        return await self._request(
            "POST",
            self.card_path,
            api_key,
            {
                "gtin": gtin,
                "tnved": tnved,
                "productGroup": product_group,
                "productCategory": category_code,
            },
        )

    async def create_aggregation(
        self,
        api_key: str,
        business_place_id: int,
        parent_code: str,
        child_codes: list[str],
    ) -> dict[str, Any]:
        report = {
            "aggregationUnits": [
                {
                    "aggregationItemsCount": len(child_codes),
                    "aggregationUnitCapacity": len(child_codes),
                    "codes": child_codes,
                    "shouldBeUnbundled": True,
                    "unitSerialNumber": parent_code,
                }
            ],
            "businessPlaceId": business_place_id,
            "documentDate": datetime.now(timezone.utc).isoformat(),
        }
        document_body = base64.b64encode(
            json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode()
        ).decode()
        return await self._request(
            "POST",
            self.aggregation_path,
            api_key,
            {"documentBody": document_body},
        )
