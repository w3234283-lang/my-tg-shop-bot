import asyncio
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, ContentType
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ============= КОНФИГУРАЦИЯ =============
BOT_TOKEN = "8755669309:AAG0i_Ql42SevYNgzdvJvRVCEYPe3ttK2XU"
ADMIN_IDS = [7921743592]  # Замените на ID админов


# ============= БАЗА ДАННЫХ =============
class Database:
    def __init__(self, filename="database.json"):
        self.filename = filename
        self.data = self.load()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "start_message": {
                "text": "👋 <b>Добро пожаловать!</b>\n\nВыберите товар для покупки:",
                "media_type": None,
                "media_id": None
            },
            "products": {},
            "orders": [],
            "stats": {"total_orders": 0, "total_revenue": 0}
        }

    def save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def add_product(self, product_id, name, description, price, material):
        self.data["products"][product_id] = {
            "name": name,
            "description": description,
            "price": price,
            "material": material,
            "created_at": datetime.now().isoformat()
        }
        self.save()

    def get_products(self):
        return self.data["products"]

    def get_product(self, product_id):
        return self.data["products"].get(product_id)

    def delete_product(self, product_id):
        if product_id in self.data["products"]:
            del self.data["products"][product_id]
            self.save()

    def add_order(self, user_id, username, product_id, product_name, price):
        order = {
            "user_id": user_id,
            "username": username,
            "product_id": product_id,
            "product_name": product_name,
            "price": price,
            "date": datetime.now().isoformat()
        }
        self.data["orders"].append(order)
        self.data["stats"]["total_orders"] += 1
        self.data["stats"]["total_revenue"] += price
        self.save()

    def get_stats(self):
        return self.data["stats"]

    def set_start_message(self, text, media_type=None, media_id=None):
        self.data["start_message"] = {
            "text": text,
            "media_type": media_type,
            "media_id": media_id
        }
        self.save()

    def get_start_message(self):
        return self.data["start_message"]


db = Database()


# ============= FSM СОСТОЯНИЯ =============
class AdminStates(StatesGroup):
    waiting_product_name = State()
    waiting_product_description = State()
    waiting_product_price = State()
    waiting_product_material = State()
    waiting_start_text = State()
    waiting_start_media = State()


# ============= КЛАВИАТУРЫ =============
def get_main_keyboard():
    products = db.get_products()
    keyboard = []
    for pid, product in products.items():
        keyboard.append([InlineKeyboardButton(
            text=f"🛍 {product['name']} - {product['price']} ⭐",
            callback_data=f"buy_{pid}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="📋 Список товаров", callback_data="admin_list_products")],
        [InlineKeyboardButton(text="✏️ Изменить /start", callback_data="admin_edit_start")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_manage_keyboard(product_id):
    keyboard = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_delete_{product_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_list_products")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ])


# ============= РОУТЕР =============
router = Router()


# ============= ПРОВЕРКА АДМИНА =============
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ============= ОБРАБОТЧИКИ =============
@router.message(Command("start"))
async def cmd_start(message: Message):
    start_msg = db.get_start_message()
    keyboard = get_main_keyboard()

    if start_msg["media_type"] and start_msg["media_id"]:
        if start_msg["media_type"] == "photo":
            await message.answer_photo(
                photo=start_msg["media_id"],
                caption=start_msg["text"],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif start_msg["media_type"] == "video":
            await message.answer_video(
                video=start_msg["media_id"],
                caption=start_msg["text"],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif start_msg["media_type"] == "animation":
            await message.answer_animation(
                animation=start_msg["media_id"],
                caption=start_msg["text"],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
    else:
        await message.answer(start_msg["text"], reply_markup=keyboard, parse_mode=ParseMode.HTML)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели!")
        return

    await message.answer(
        "<b>🔧 Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )


# ============= ПОКУПКА ТОВАРА =============
@router.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: CallbackQuery):
    try:
        # Получаем ID товара
        product_id = callback.data.replace("buy_", "")

        # Отладочная информация
        print(f"DEBUG: Нажата кнопка buy, product_id = {product_id}")
        print(f"DEBUG: Все товары в БД: {list(db.get_products().keys())}")

        product = db.get_product(product_id)

        if not product:
            await callback.answer("❌ Товар не найден!", show_alert=True)
            await callback.message.answer(
                f"❌ Ошибка: товар с ID '{product_id}' не найден в базе данных.\n"
                f"Доступные товары: {', '.join(db.get_products().keys())}"
            )
            return

        await callback.answer()

        prices = [LabeledPrice(label=product["name"], amount=product["price"])]

        await callback.message.answer_invoice(
            title=product["name"],
            description=product["description"],
            payload=f"product_{product_id}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}\n\nCallback data: {callback.data}")


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    try:
        payment = message.successful_payment
        # Получаем ID товара из payload
        product_id = payment.invoice_payload.replace("product_", "")

        # Отладка
        print(f"DEBUG: Успешная оплата, product_id = {product_id}")
        print(f"DEBUG: Payload = {payment.invoice_payload}")
        print(f"DEBUG: Все товары в БД: {list(db.get_products().keys())}")

        product = db.get_product(product_id)

        if not product:
            await message.answer(
                f"❌ Ошибка при получении товара!\n\n"
                f"ID товара: {product_id}\n"
                f"Доступные товары: {', '.join(db.get_products().keys())}\n\n"
                f"Обратитесь к администратору!"
            )
            # Уведомляем админов
            for admin_id in ADMIN_IDS:
                try:
                    await message.bot.send_message(
                        admin_id,
                        f"⚠️ ОШИБКА! Пользователь @{message.from_user.username or message.from_user.id} "
                        f"оплатил товар {product_id}, но товар не найден в БД!"
                    )
                except:
                    pass
            return

        # Сохраняем заказ
        db.add_order(
            message.from_user.id,
            message.from_user.username or "Без username",
            product_id,
            product["name"],
            product["price"]
        )

        # Отправляем подтверждение
        await message.answer(
            f"✅ <b>Спасибо за покупку!</b>\n\n"
            f"Товар: {product['name']}\n"
            f"Цена: {product['price']} ⭐",
            parse_mode=ParseMode.HTML
        )

        # Отправляем материал
        material = product["material"]

        if material["type"] == "text":
            await message.answer(
                f"📄 <b>Ваш материал:</b>\n\n{material['content']}",
                parse_mode=ParseMode.HTML
            )
        elif material["type"] == "file":
            await message.answer_document(
                document=material["file_id"],
                caption="📄 Ваш материал"
            )
        elif material["type"] == "photo":
            await message.answer_photo(
                photo=material["file_id"],
                caption="📄 Ваш материал"
            )
        elif material["type"] == "video":
            await message.answer_video(
                video=material["file_id"],
                caption="📄 Ваш материал"
            )

        # Уведомляем админов о продаже
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(
                    admin_id,
                    f"💰 <b>Новая продажа!</b>\n\n"
                    f"Товар: {product['name']}\n"
                    f"Цена: {product['price']} ⭐\n"
                    f"Покупатель: @{message.from_user.username or message.from_user.id}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass

    except Exception as e:
        await message.answer(f"❌ Критическая ошибка: {str(e)}")
        print(f"ERROR в successful_payment: {e}")


# ============= АДМИН: ДОБАВИТЬ ТОВАР =============
@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    await callback.message.edit_text(
        "📝 <b>Добавление товара</b>\n\nВведите название товара:",
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_product_name)
    await callback.answer()


@router.message(AdminStates.waiting_product_name)
async def admin_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(
        "📝 Введите описание товара:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_product_description)


@router.message(AdminStates.waiting_product_description)
async def admin_product_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "💰 Введите цену в звездах (целое число):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_product_price)


@router.message(AdminStates.waiting_product_price)
async def admin_product_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректную цену (целое положительное число)!")
        return

    await state.update_data(price=price)
    await message.answer(
        "📦 <b>Отправьте материал товара:</b>\n\n"
        "Вы можете отправить:\n"
        "• Текст\n"
        "• Фото\n"
        "• Видео\n"
        "• Файл",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_product_material)


@router.message(AdminStates.waiting_product_material)
async def admin_product_material(message: Message, state: FSMContext):
    material = {}

    if message.text:
        material = {"type": "text", "content": message.text}
    elif message.photo:
        material = {"type": "photo", "file_id": message.photo[-1].file_id}
    elif message.video:
        material = {"type": "video", "file_id": message.video.file_id}
    elif message.document:
        material = {"type": "file", "file_id": message.document.file_id}
    else:
        await message.answer("❌ Неподдерживаемый тип материала!")
        return

    data = await state.get_data()
    # Генерируем уникальный ID для товара
    import time
    product_id = f"prod_{int(time.time())}"

    db.add_product(
        product_id,
        data["name"],
        data["description"],
        data["price"],
        material
    )

    await message.answer(
        f"✅ <b>Товар успешно добавлен!</b>\n\n"
        f"Название: {data['name']}\n"
        f"Описание: {data['description']}\n"
        f"Цена: {data['price']} ⭐",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()


# ============= АДМИН: СПИСОК ТОВАРОВ =============
@router.callback_query(F.data == "admin_list_products")
async def admin_list_products(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    products = db.get_products()

    if not products:
        await callback.message.edit_text(
            "📋 <b>Список товаров пуст</b>",
            reply_markup=get_admin_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return

    keyboard = []
    for pid, product in products.items():
        keyboard.append([InlineKeyboardButton(
            text=f"{product['name']} - {product['price']} ⭐",
            callback_data=f"admin_view_{pid}"
        )])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")])

    await callback.message.edit_text(
        "📋 <b>Список товаров:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_"))
async def admin_view_product(callback: CallbackQuery):
    product_id = callback.data.replace("admin_view_", "")
    product = db.get_product(product_id)

    if not product:
        await callback.answer("❌ Товар не найден!", show_alert=True)
        return

    text = (
        f"🛍 <b>{product['name']}</b>\n\n"
        f"📝 Описание: {product['description']}\n"
        f"💰 Цена: {product['price']} ⭐\n"
        f"📦 Материал: {product['material']['type']}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_product_manage_keyboard(product_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_"))
async def admin_delete_product(callback: CallbackQuery):
    product_id = callback.data.replace("admin_delete_", "")
    db.delete_product(product_id)

    await callback.answer("✅ Товар удален!", show_alert=True)
    await admin_list_products(callback)


# ============= АДМИН: ИЗМЕНИТЬ /START =============
@router.callback_query(F.data == "admin_edit_start")
async def admin_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    await callback.message.edit_text(
        "✏️ <b>Изменение приветственного сообщения</b>\n\n"
        "Отправьте новый текст для /start:",
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_start_text)
    await callback.answer()


@router.message(AdminStates.waiting_start_text)
async def admin_start_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer(
        "📸 <b>Отправьте медиа (фото/видео/гиф)</b>\n\n"
        "Или отправьте /skip чтобы пропустить",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_start_media)


@router.message(AdminStates.waiting_start_media, Command("skip"))
async def admin_start_media_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    db.set_start_message(data["text"])

    await message.answer(
        "✅ Приветственное сообщение обновлено!",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


@router.message(AdminStates.waiting_start_media)
async def admin_start_media(message: Message, state: FSMContext):
    media_type = None
    media_id = None

    if message.photo:
        media_type = "photo"
        media_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_id = message.video.file_id
    elif message.animation:
        media_type = "animation"
        media_id = message.animation.file_id
    else:
        await message.answer("❌ Отправьте фото, видео или гиф!")
        return

    data = await state.get_data()
    db.set_start_message(data["text"], media_type, media_id)

    await message.answer(
        "✅ Приветственное сообщение обновлено с медиа!",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


# ============= АДМИН: СТАТИСТИКА =============
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return

    stats = db.get_stats()
    products_count = len(db.get_products())

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"🛍 Товаров: {products_count}\n"
        f"📦 Заказов: {stats['total_orders']}\n"
        f"💰 Доход: {stats['total_revenue']} ⭐"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ============= АДМИН: ОТМЕНА/НАЗАД =============
@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "<b>🔧 Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer("❌ Действие отменено")


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🔧 Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ============= ЗАПУСК БОТА =============
async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())