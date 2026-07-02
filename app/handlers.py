import asyncio
import json
from contextlib import suppress
from html import escape
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message

from app.asl_client import AslApiError, AslClient
from app.code_files import read_codes, select_full_marking_codes
from app.datamatrix_pdf import create_datamatrix_pdf
from app.keyboards import cancel_menu, datamatrix_product_menu, main_menu
from app.states import AggregationFlow, ApiKeyFlow, DataMatrixFlow
from app.storage import UserStorage


def create_router(storage: UserStorage, asl: AslClient) -> Router:
    router = Router()

    async def request_key_or_continue(message: Message, state: FSMContext, action: str) -> bool:
        api_key = storage.get_api_key(message.from_user.id)
        if api_key:
            return True
        await state.update_data(action_after_key=action)
        await state.set_state(ApiKeyFlow.waiting_for_key)
        await message.answer(
            "Asl Belgisi API kalitingizni yuboring.\n"
            "Kalit shifrlangan holda saqlanadi va faqat API so'rovlari uchun ishlatiladi.",
            reply_markup=cancel_menu(),
        )
        return False

    async def begin_action(message: Message, state: FSMContext, action: str) -> None:
        if not await request_key_or_continue(message, state, action):
            return
        business_place_id = storage.get_business_place_id(message.from_user.id)
        if business_place_id:
            await state.update_data(business_place_id=business_place_id)
        await state.set_state(AggregationFlow.waiting_for_parent)
        await message.answer("1. Групповой кодни киритинг:", reply_markup=cancel_menu())

    @router.message(CommandStart())
    async def start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "Asl Belgisi markirovka botiga xush kelibsiz.\nKerakli amalni tanlang:",
            reply_markup=main_menu(),
        )

    @router.message(F.text == "Bekor qilish")
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Amal bekor qilindi.", reply_markup=main_menu())

    @router.message(F.text == "API kalitni almashtirish")
    async def replace_key(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.update_data(action_after_key="menu")
        await state.set_state(ApiKeyFlow.waiting_for_key)
        await message.answer("Yangi Asl Belgisi API kalitini yuboring:", reply_markup=cancel_menu())

    @router.message(F.text == "Agregatsiya")
    async def aggregation_start(message: Message, state: FSMContext) -> None:
        await begin_action(message, state, "aggregation")

    @router.message(F.text.in_({"Excel/CSV -> DataMatrix PDF", "Excel/CSV → DataMatrix PDF"}))
    async def datamatrix_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(DataMatrixFlow.waiting_for_product_type)
        await message.answer(
            "Mahsulot turini tanlang:",
            reply_markup=datamatrix_product_menu(),
        )

    @router.message(
        DataMatrixFlow.waiting_for_product_type,
        F.text.in_({"Suv mahsuloti", "Maishiy texnika", "Mineral o'g'itlar"}),
    )
    async def datamatrix_product_type(message: Message, state: FSMContext) -> None:
        await state.update_data(product_type=message.text)
        await state.set_state(DataMatrixFlow.waiting_for_file)
        await message.answer(
            f"Tanlandi: {escape(message.text or '')}\n\n"
            "Kodlar joylashgan .xlsx yoki .csv faylni yuboring.",
            reply_markup=cancel_menu(),
        )

    @router.message(DataMatrixFlow.waiting_for_file)
    async def datamatrix_file(message: Message, state: FSMContext) -> None:
        document = message.document
        if not document:
            await message.answer(".xlsx yoki .csv fayl yuboring.")
            return
        if document.file_size and document.file_size > 20 * 1024 * 1024:
            await message.answer("Fayl hajmi 20 MB dan oshmasligi kerak.")
            return

        buffer = BytesIO()
        await message.bot.download(document, destination=buffer)
        try:
            raw_codes = await asyncio.to_thread(
                read_codes, document.file_name or "codes", buffer.getvalue()
            )
            data = await state.get_data()
            product_type = data.get("product_type", "Mahsulot")
            codes = select_full_marking_codes(raw_codes, product_type)
            if not codes:
                if product_type == "Mineral o'g'itlar":
                    raise ValueError("Faylda 01+21+<GS>93 formatdagi kod topilmadi.")
                raise ValueError("Faylda 01+21+<GS>91+<GS>92 formatdagi kod topilmadi.")
            pdf = await asyncio.to_thread(create_datamatrix_pdf, codes, product_type)
        except Exception as exc:
            await message.answer(f"Faylni qayta ishlab bo'lmadi: {escape(str(exc))}")
            return

        if product_type == "Suv mahsuloti":
            file_prefix = "suv-mahsuloti"
        elif product_type == "Maishiy texnika":
            file_prefix = "maishiy-texnika"
        else:
            file_prefix = "mineral-ogitlar"
        await message.answer_document(
            BufferedInputFile(pdf, filename=f"{file_prefix}-datamatrix.pdf"),
            caption=(
                f"{escape(product_type)}: {len(codes)} ta kod "
                "DataMatrix PDF formatiga aylantirildi."
            ),
            reply_markup=main_menu(),
        )
        await state.clear()

    @router.message(ApiKeyFlow.waiting_for_key)
    async def save_key(message: Message, state: FSMContext) -> None:
        api_key = (message.text or "").strip()
        with suppress(Exception):
            await message.delete()
        if len(api_key) < 8:
            await message.answer("API kalit juda qisqa. To'g'ri kalitni yuboring.")
            return
        try:
            await asl.check_api_key(api_key)
        except AslApiError as exc:
            await message.answer(f"API kalit tekshirilmadi.\n{escape(str(exc))}")
            return

        storage.save_api_key(message.from_user.id, api_key)
        data = await state.get_data()
        action = data.get("action_after_key", "menu")
        await state.clear()
        await message.answer("API kalit tasdiqlandi va xavfsiz saqlandi.", reply_markup=main_menu())
        if action == "aggregation":
            await begin_action(message, state, action)

    @router.message(AggregationFlow.waiting_for_business_place_address)
    async def aggregation_business_place_address(message: Message, state: FSMContext) -> None:
        address = (message.text or "").strip()
        if len(address) < 5:
            await message.answer("Manzilni to'liqroq kiriting.")
            return
        storage.save_business_place_address(message.from_user.id, address)
        await state.set_state(AggregationFlow.waiting_for_business_place)
        await message.answer(
            "Manzil saqlandi. xTrace API uchun shu joyning raqamli ID sini bir marta kiriting:"
        )

    @router.message(AggregationFlow.waiting_for_business_place)
    async def aggregation_business_place(message: Message, state: FSMContext) -> None:
        value = (message.text or "").strip()
        if not value.isdigit():
            await message.answer("Business Place ID faqat raqam bo'lishi kerak.")
            return
        business_place_id = int(value)
        storage.save_business_place_id(message.from_user.id, business_place_id)
        await state.update_data(business_place_id=business_place_id)
        data = await state.get_data()
        child_codes = data.get("pending_child_codes")
        if child_codes:
            await send_aggregation(message, state, child_codes)
        else:
            await state.set_state(AggregationFlow.waiting_for_parent)
            await message.answer("1. Групповой кодни киритинг:")

    @router.message(AggregationFlow.waiting_for_parent)
    async def aggregation_parent(message: Message, state: FSMContext) -> None:
        if message.document:
            buffer = BytesIO()
            await message.bot.download(message.document, destination=buffer)
            try:
                parent_codes = await asyncio.to_thread(
                    read_codes,
                    message.document.file_name or "group-codes.xlsx",
                    buffer.getvalue(),
                )
            except Exception as exc:
                await message.answer(f"Групповой код файлини ўқиб бўлмади: {escape(str(exc))}")
                return
        else:
            parent_codes = [
                line.strip()
                for line in (message.text or "").replace("\r\n", "\n").split("\n")
                if line.strip()
            ]
        if not parent_codes or any(len(code) < 5 for code in parent_codes):
            await message.answer("Parent kod noto'g'ri ko'rinmoqda. Qayta kiriting.")
            return
        if len(parent_codes) > 200_000:
            await message.answer("Групповой кодлар сони 200 000 тадан ошмаслиги керак.")
            return
        await state.update_data(parent_codes=parent_codes)
        await state.set_state(AggregationFlow.waiting_for_units_per_group)
        await message.answer(
            f"{len(parent_codes)} ta Групповой код qabul qilindi.\n"
            "1 ta Групповой код ichida nechta Единица товара bo'lishini kiriting:"
        )

    @router.message(AggregationFlow.waiting_for_units_per_group)
    async def aggregation_units_per_group(message: Message, state: FSMContext) -> None:
        value = (message.text or "").strip()
        if not value.isdigit() or int(value) < 1:
            await message.answer("Miqdorni raqam bilan kiriting. Masalan: 20")
            return
        units_per_group = int(value)
        if units_per_group > 200_000:
            await message.answer("Bitta gruppada maksimum 200 000 ta birlik bo'lishi mumkin.")
            return
        await state.update_data(units_per_group=units_per_group)
        await state.set_state(AggregationFlow.waiting_for_children)
        await message.answer(
            "2. Единица товара кодларини юборинг.\n"
            "1-200 000 ta kod qabul qilinadi.\n"
            "Ko'p kod bo'lsa .csv yoki .xlsx fayl yuboring."
        )

    async def send_aggregation(
        message: Message, state: FSMContext, child_codes: list[str]
    ) -> None:
        data = await state.get_data()
        api_key = storage.get_api_key(message.from_user.id)
        await message.answer(
            f"{len(child_codes)} ta Единица товара kodi agregatsiyaga yuborilmoqda..."
        )
        parent_codes = data["parent_codes"]
        units_per_group = data["units_per_group"]
        expected_count = len(parent_codes) * units_per_group
        if len(child_codes) != expected_count:
            await message.answer(
                f"Кодлар сони нотўғри.\nКерак: {expected_count} та "
                f"({len(parent_codes)} x {units_per_group}).\nЮборилди: {len(child_codes)} та."
            )
            return
        results = []
        success_count = 0
        error_count = 0
        for index, parent_code in enumerate(parent_codes):
            start = index * units_per_group
            group_children = child_codes[start : start + units_per_group]
            try:
                await asl.create_aggregation(
                    api_key,
                    data["business_place_id"],
                    parent_code,
                    group_children,
                )
                results.append(f"{index + 1}. OK: {parent_code}")
                success_count += 1
            except AslApiError as exc:
                if exc.status_code == 400 and "businessPlaceId" in str(exc):
                    storage.clear_business_place_id(message.from_user.id)
                    await state.update_data(pending_child_codes=child_codes)
                    await state.set_state(AggregationFlow.waiting_for_business_place)
                    await message.answer(
                        "Saqlangan Business Place ID noto'g'ri. To'g'ri raqamli ID ni kiriting:"
                    )
                    return
                results.append(f"{index + 1}. XATO: {parent_code} - {exc}")
                error_count += 1
        await message.answer(
            "Agregatsiya yakunlandi.\n"
            f"Jami yuborildi: {len(parent_codes)}\n"
            f"Muvaffaqiyatli: {success_count}\n"
            f"Xatolik: {error_count}\n\n"
            + escape("\n".join(results[:30])),
            reply_markup=main_menu(),
        )
        storage.delete_api_key(message.from_user.id)
        await state.clear()

    @router.message(AggregationFlow.waiting_for_children)
    async def aggregation_children(message: Message, state: FSMContext) -> None:
        if message.document:
            buffer = BytesIO()
            await message.bot.download(message.document, destination=buffer)
            try:
                child_codes = await asyncio.to_thread(
                    read_codes,
                    message.document.file_name or "codes.csv",
                    buffer.getvalue(),
                )
            except Exception as exc:
                await message.answer(f"Faylni o'qib bo'lmadi: {escape(str(exc))}")
                return
        else:
            child_codes = [
                line.strip()
                for line in (message.text or "").replace("\r\n", "\n").split("\n")
                if line.strip()
            ]
        if not child_codes:
            await message.answer("Kamida bitta ichki kod yuboring.")
            return
        if len(child_codes) > 200_000:
            await message.answer(
                f"Juda ko'p kod: {len(child_codes)} ta. Maksimum 200 000 ta kod."
            )
            return
        data = await state.get_data()
        if not data.get("business_place_id"):
            await state.update_data(pending_child_codes=child_codes)
            await state.set_state(AggregationFlow.waiting_for_business_place)
            await message.answer("Business Place raqamli ID sini kiriting:")
            return
        await send_aggregation(message, state, child_codes)

    return router
