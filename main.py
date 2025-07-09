import os
import logging
from typing import Dict, List, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
import asyncio
import traceback
import uuid
import time
from datetime import datetime

# إعداد تسجيل الأخطاء المفصل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# قراءة المتغيرات من البيئة (Render Environment Variables)
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')  # معرف القناة الرقمي (مثل: -1001234567890)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # اسم القناة بدون @ (مثل: my_channel)
DEVELOPER_USERNAME = os.getenv('DEVELOPER_USERNAME')  # اسم المطور بدون @
PORT = int(os.getenv('PORT', 8080))  # منفذ الخادم الافتراضي لـ Render

# التحقق من وجود المتغيرات المطلوبة
if not BOT_TOKEN:
    raise ValueError("يجب تعيين BOT_TOKEN في متغيرات البيئة")
if not CHANNEL_ID:
    raise ValueError("يجب تعيين CHANNEL_ID في متغيرات البيئة")
if not CHANNEL_USERNAME:
    raise ValueError("يجب تعيين CHANNEL_USERNAME في متغيرات البيئة")
if not DEVELOPER_USERNAME:
    raise ValueError("يجب تعيين DEVELOPER_USERNAME في متغيرات البيئة")

# إنشاء كائنات البوت والموزع
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# حالات المحادثة
class XOStates(StatesGroup):
    waiting_subscription = State()
    main_menu = State()
    choosing_symbols = State()  # حالة جديدة لاختيار الرموز
    in_game = State()

# تخزين بيانات الألعاب في الذاكرة
# هيكل: {user_id: {game_id: game_data}}
games: Dict[int, Dict[str, Dict]] = {}

# === دوال اكتشاف الأخطاء ===

def debug_callback_data(callback: types.CallbackQuery, function_name: str):
    """طباعة معلومات مفصلة عن الاستدعاء لأغراض التشخيص"""
    logger.info(f"=== تشخيص {function_name} ===")
    logger.info(f"Callback ID: {callback.id}")
    logger.info(f"Callback Data: {callback.data}")
    logger.info(f"User ID: {callback.from_user.id}")
    logger.info(f"Username: {callback.from_user.username}")
    logger.info(f"First Name: {callback.from_user.first_name}")

    if callback.message:
        logger.info(f"Message ID: {callback.message.message_id}")
        logger.info(f"Chat ID: {callback.message.chat.id}")
        logger.info(f"Chat Type: {callback.message.chat.type}")
        if hasattr(callback.message.chat, 'title'):
            logger.info(f"Chat Title: {callback.message.chat.title}")
    else:
        logger.error("❌ callback.message is None!")

    if callback.inline_message_id:
        logger.info(f"Inline Message ID: {callback.inline_message_id}")

    logger.info(f"=== نهاية تشخيص {function_name} ===")

def safe_callback_handler(func):
    """مُزخرف لالتقاط الأخطاء في معالجات الاستدعاءات"""
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs):
        try:
            debug_callback_data(callback, func.__name__)
            return await func(callback, *args)
        except Exception as e:
            logger.error(f"خطأ في {func.__name__}: {str(e)}")
            logger.error(f"تفاصيل الخطأ: {traceback.format_exc()}")

            # محاولة إرسال رسالة خطأ للمستخدم
            try:
                if callback.message:
                    await callback.answer("حدث خطأ! يرجى المحاولة مرة أخرى.", show_alert=True)
                else:
                    await callback.answer("خطأ في النظام", show_alert=True)
            except Exception as answer_error:
                logger.error(f"فشل في إرسال رسالة الخطأ: {answer_error}")

    return wrapper

# === دوال مساعدة ===

def create_main_menu_keyboard():
    """إنشاء لوحة مفاتيح الشاشة الرئيسية"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 ابدأ التحدي الآن!", callback_data="start_challenge")],
        [InlineKeyboardButton(text="📚 تعلم كيفية اللعب", callback_data="how_to_play")],
        [InlineKeyboardButton(text="💬 تواصل مع المطور", url=f"https://t.me/{DEVELOPER_USERNAME}")]
    ])
    return keyboard

def create_subscription_keyboard():
    """إنشاء لوحة مفاتيح التحقق من الاشتراك"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 انضم للقناة الآن", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="✅ لقد انضممت، تحقق الآن!", callback_data="check_subscription")]
    ])
    return keyboard

def create_game_board(game_data: Dict, game_id: str) -> InlineKeyboardMarkup:
    """إنشاء شبكة اللعبة 3x3"""
    board = game_data['board']
    keyboard = []

    # إنشاء شبكة 3x3 من الأزرار
    for i in range(3):
        row = []
        for j in range(3):
            pos = i * 3 + j
            text = board[pos] if board[pos] else "⬜"
            callback_data = f"move_{game_id}_{pos}"
            row.append(InlineKeyboardButton(text=text, callback_data=callback_data))
        keyboard.append(row)

    # إضافة أزرار التحكم
    control_buttons = []

    # زر إعادة اللعب (متاح في أي وقت)
    control_buttons.append(InlineKeyboardButton(text="🔄 إعادة اللعبة", callback_data=f"reset_{game_id}"))
    
    # زر حذف اللعبة (متاح دائماً)
    control_buttons.append(InlineKeyboardButton(text="🗑️ حذف اللعبة", callback_data=f"delete_{game_id}"))

    if control_buttons:
        keyboard.append(control_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def check_winner(board: List[str]) -> Optional[str]:
    """فحص الفائز في اللعبة"""
    # خطوط الفوز المحتملة
    winning_lines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # الصفوف
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # الأعمدة
        [0, 4, 8], [2, 4, 6]              # الأقطار
    ]

    for line in winning_lines:
        if board[line[0]] and board[line[0]] == board[line[1]] == board[line[2]]:
            return board[line[0]]

    return None

def is_board_full(board: List[str]) -> bool:
    """فحص امتلاء الشبكة (تعادل)"""
    return all(cell != "" for cell in board)

async def check_user_subscription(user_id: int) -> bool:
    """التحقق من اشتراك المستخدم في القناة"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def create_unique_game_id():
    """إنشاء معرف فريد للعبة"""
    return str(uuid.uuid4())

def find_game_by_id(game_id: str):
    """البحث عن اللعبة في جميع المستخدمين"""
    for user_id, user_games in games.items():
        if game_id in user_games:
            return user_id, user_games[game_id]
    return None, None

# === معالجات الأوامر ===

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """معالج أمر /start"""
    user_id = message.from_user.id
    logger.info(f"مستخدم جديد بدأ البوت: {user_id}")

    # التحقق من اشتراك المستخدم
    is_subscribed = await check_user_subscription(user_id)

    if not is_subscribed:
        # إرسال رسالة طلب الاشتراك
        welcome_subscription_text = """
🎮 أهلاً وسهلاً! مرحباً بك في بوت XO الرائع!

🔔 للاستمتاع بجميع الميزات المذهلة، يرجى الانضمام لقناتنا أولاً

✨ ستحصل على:
• ألعاب لا محدودة مع الأصدقاء
• تحديثات جديدة ومثيرة
• مسابقات وجوائز حصرية

👇 انضم الآن ولنبدأ المتعة!
        """
        await message.answer(
            welcome_subscription_text,
            reply_markup=create_subscription_keyboard()
        )
        await state.set_state(XOStates.waiting_subscription)
    else:
        # الانتقال للشاشة الرئيسية
        await show_main_menu(message)
        await state.set_state(XOStates.main_menu)

async def show_main_menu(message: types.Message):
    """عرض الشاشة الرئيسية"""
    welcome_text = """
🎯 مرحباً بك في عالم لعبة XO المثيرة!

⚡ اختبر مهاراتك في أشهر لعبة استراتيجية
🏆 تحدَّ أصدقاءك واستمتع بالمنافسة
🎮 لعبة سريعة ومسلية في أي وقت

ماذا تريد أن تفعل؟
    """
    await message.answer(
        welcome_text,
        reply_markup=create_main_menu_keyboard()
    )

# === معالجات الاستدعاءات (Callbacks) ===

@dp.callback_query(lambda c: c.data == "check_subscription")
@safe_callback_handler
async def check_subscription_callback(callback: types.CallbackQuery):
    """معالج زر التحقق من الاشتراك"""
    user_id = callback.from_user.id

    is_subscribed = await check_user_subscription(user_id)

    if not is_subscribed:
        await callback.answer("يجب الاشتراك أولاً.", show_alert=True)
        return

    # إذا اشترك المستخدم
    await callback.message.edit_text(
        """
🎉 رائع! تم التحقق بنجاح!

🎯 مرحباً بك في عالم لعبة XO المثيرة!

⚡ اختبر مهاراتك في أشهر لعبة استراتيجية
🏆 تحدَّ أصدقاءك واستمتع بالمنافسة
🎮 لعبة سريعة ومسلية في أي وقت

ماذا تريد أن تفعل؟
        """,
        reply_markup=create_main_menu_keyboard()
    )
    await callback.answer("تم التحقق بنجاح!")

@dp.callback_query(lambda c: c.data == "how_to_play")
@safe_callback_handler
async def how_to_play_callback(callback: types.CallbackQuery):
    """معالج زر كيفية اللعب"""
    instructions = """
📖 كيفية اللعب:

1️⃣ ابدأ التحدي: اضغط على "🔥 ابدأ التحدي الآن!"

2️⃣ اختر المحادثة: اضغط على "▶️ اختر المحادثة" واختر الدردشة التي تريد إرسال التحدي إليها

3️⃣ أرسل التحدي: سيتم إرسال رسالة التحدي تلقائياً في الدردشة المختارة

4️⃣ الانضمام للعبة: 
   • يجب على كلا اللاعبين الضغط على "🎮 انضم للعبة"
   • اللاعب الأول الذي يضغط يصبح ❌ (إكس)
   • اللاعب الثاني الذي يضغط يصبح ⭕ (أو)

5️⃣ ابدأ اللعب: 
   • ستظهر شبكة 3×3 بعد انضمام كلا اللاعبين
   • اضغط على المربعات للعب
   • اللعب بالتناوب - اللاعب الأول (❌) يبدأ

6️⃣ الفوز: اربط 3 رموز متتالية (أفقياً، عمودياً، أو قطرياً)

7️⃣ إعادة اللعب: بعد انتهاء الجولة يمكنك الضغط على "🎮 اقبل التحدي الجديد!"
   • ملاحظة: عند إعادة اللعب يتم تبديل الأدوار تلقائياً!

🎯 اللاعب الأول: ❌ (إكس) - يبدأ اللعب
🎯 اللاعب الثاني: ⭕ (أو) - يلعب بعد الأول
⚡ التناوب: كل لاعب يلعب في دوره فقط
🔄 تبديل الأدوار: عند إعادة اللعب يصبح اللاعب الثاني هو الأول والعكس
    """

    # إنشاء لوحة مفاتيح مع زر العودة
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    await callback.message.edit_text(
        instructions,
        reply_markup=back_keyboard
    )

@dp.callback_query(lambda c: c.data == "start_challenge")
@safe_callback_handler
async def start_challenge_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالج زر تحدي اللعبة"""
    # الانتقال إلى حالة اختيار الرموز
    await state.set_state(XOStates.choosing_symbols)
    
    # إنشاء لوحة مفاتيح اختيار الرموز
    symbols_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔤 إضافة رمز مخصص", callback_data="custom_symbols")],
        [InlineKeyboardButton(text="⚪ الرموز الافتراضية", callback_data="default_symbols")],
        [InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_main")]
    ])
    
    symbols_message = """
🎮 إعدادات الرموز:

يمكنك اختيار رموز مخصصة للاعبين بدلاً من الرموز الافتراضية (❌ و ⭕)

🔤 إضافة رمز مخصص: اختر رمزاً لكل لاعب
⚪ الرموز الافتراضية: استخدم ❌ و ⭕

👇 اختر الخيار المناسب لك:
    """
    
    await callback.message.edit_text(
        symbols_message,
        reply_markup=symbols_keyboard
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "custom_symbols")
@safe_callback_handler
async def custom_symbols_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الرموز المخصصة"""
    # حفظ اختيار الرموز المخصصة في حالة المستخدم
    await state.update_data(symbols_type="custom")
    
    # طلب إدخال رمز اللاعب الأول
    await callback.message.edit_text(
        "📝 الرجاء إرسال الرمز الذي تريده للاعب الأول (مثل: 🔥، ⭐، إلخ):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_symbols")]
        ])
    )
    await callback.answer("الرجاء إرسال رمز للاعب الأول")

@dp.callback_query(lambda c: c.data == "default_symbols")
@safe_callback_handler
async def default_symbols_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالج اختيار الرموز الافتراضية"""
    # حفظ اختيار الرموز الافتراضية في حالة المستخدم
    await state.update_data(symbols_type="default", player1_symbol="❌", player2_symbol="⭕")
    
    # متابعة إلى إنشاء التحدي
    await create_challenge(callback, state)
    await callback.answer("تم اختيار الرموز الافتراضية")

@dp.callback_query(lambda c: c.data == "back_to_symbols")
@safe_callback_handler
async def back_to_symbols_callback(callback: types.CallbackQuery, state: FSMContext):
    """العودة إلى شاشة اختيار الرموز"""
    await state.set_state(XOStates.choosing_symbols)
    
    symbols_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔤 إضافة رمز مخصص", callback_data="custom_symbols")],
        [InlineKeyboardButton(text="⚪ الرموز الافتراضية", callback_data="default_symbols")],
        [InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        "🎮 إعدادات الرموز:\n\nاختر خياراً لرموز اللاعبين:",
        reply_markup=symbols_keyboard
    )
    await callback.answer()

async def create_challenge(callback: types.CallbackQuery, state: FSMContext):
    """إنشاء التحدي بعد اختيار الرموز"""
    # استرجاع بيانات الرموز
    user_data = await state.get_data()
    symbols_type = user_data.get("symbols_type", "default")
    
    if symbols_type == "custom":
        # إذا كان المستخدم يريد رموزاً مخصصة، انتظر رموزه
        return
    
    # إنشاء لوحة مفاتيح اختيار المحادثة
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ اختر المحادثة", switch_inline_query="play_xo")],
        [InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    challenge_message = """
🎯 حان وقت التحدي!

🔥 اضغط الزر أدناه لاختيار المحادثة
📤 سيتم إرسال تحدي مثير لأصدقائك
⚡ من سيكون الفائز؟ اكتشف الآن!

👇 اختر المحادثة وابدأ المعركة!
    """
    await callback.message.edit_text(
        challenge_message,
        reply_markup=keyboard
    )
    await state.set_state(XOStates.main_menu)

@dp.message(XOStates.choosing_symbols)
async def handle_symbol_input(message: types.Message, state: FSMContext):
    """معالج إدخال الرموز المخصصة"""
    user_data = await state.get_data()
    symbols_type = user_data.get("symbols_type", "default")
    
    if symbols_type != "custom":
        return
    
    # التحقق من أن الرسالة تحتوي على رمز واحد فقط
    if len(message.text) != 1:
        await message.reply("⛔ الرجاء إدخال رمز واحد فقط (مثل: 🔥، ⭐، إلخ)")
        return
    
    # حفظ الرمز في حالة المستخدم
    user_data = await state.get_data()
    
    if "player1_symbol" not in user_data:
        # هذا هو رمز اللاعب الأول
        await state.update_data(player1_symbol=message.text)
        await message.answer(
            "📝 الرجاء إرسال الرمز الذي تريده للاعب الثاني:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_symbols")]
            ])
    elif "player2_symbol" not in user_data:
        # هذا هو رمز اللاعب الثاني
        await state.update_data(player2_symbol=message.text)
        
        # متابعة إلى إنشاء التحدي
        user_data = await state.get_data()
        await message.answer(
            f"✅ تم تعيين الرموز:\n\nاللاعب الأول: {user_data['player1_symbol']}\nاللاعب الثاني: {user_data['player2_symbol']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ متابعة", callback_data="proceed_to_challenge")]
            ])

@dp.callback_query(lambda c: c.data == "proceed_to_challenge")
@safe_callback_handler
async def proceed_to_challenge_callback(callback: types.CallbackQuery, state: FSMContext):
    """المتابعة إلى إنشاء التحدي بعد اختيار الرموز"""
    # إنشاء لوحة مفاتيح اختيار المحادثة
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ اختر المحادثة", switch_inline_query="play_xo")],
        [InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    challenge_message = """
🎯 حان وقت التحدي!

🔥 اضغط الزر أدناه لاختيار المحادثة
📤 سيتم إرسال تحدي مثير لأصدقائك
⚡ من سيكون الفائز؟ اكتشف الآن!

👇 اختر المحادثة وابدأ المعركة!
    """
    await callback.message.edit_text(
        challenge_message,
        reply_markup=keyboard
    )
    await state.set_state(XOStates.main_menu)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("join_challenge"))
@safe_callback_handler
async def join_challenge_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالج زر الانضمام للتحدي - نظام لاعبين محسن"""

    # استخراج معرف اللعبة من callback_data
    game_id = callback.data.split("_")[2]
    logger.info(f"Game ID from callback: {game_id}")

    user_id = callback.from_user.id
    username = callback.from_user.username or callback.from_user.first_name

    logger.info(f"محاولة انضمام اللاعب {username} (ID: {user_id}) للعبة {game_id}")

    # البحث عن اللعبة في جميع المستخدمين
    game_owner_id, game_data = find_game_by_id(game_id)

    # متغير لنص اللعبة
    game_text = ""

    if not game_data:
        # استرجاع بيانات الرموز من حالة المستخدم
        user_data = await state.get_data()
        player1_symbol = user_data.get('player1_symbol', '❌')
        player2_symbol = user_data.get('player2_symbol', '⭕')
        
        # إنشاء لعبة جديدة - اللاعب الأول (X)
        if user_id not in games:
            games[user_id] = {}

        games[user_id][game_id] = {
            'board': [""] * 9,
            'current_player': 'X',
            'player1_id': user_id,  # اللاعب الأول (X)
            'player2_id': None,     # في انتظار اللاعب الثاني
            'player1_username': username,
            'player2_username': None,
            'player1_symbol': player1_symbol,
            'player2_symbol': player2_symbol,
            'game_over': False,
            'winner': None,
            'waiting_for_second_player': True,
            'player1_wins': 0,  # عدد مرات فوز اللاعب الأول
            'player2_wins': 0   # عدد مرات فوز اللاعب الثاني
        }

        logger.info(f"✅ تم إنشاء لعبة جديدة {game_id} - اللاعب الأول (X): {username}")

        game_text = f"""
🎮 لعبة XO - في انتظار اللاعب الثاني!

👤 اللاعب الأول: {username} ({player1_symbol})
⏳ في انتظار اللاعب الثاني ({player2_symbol})

🔥 يحتاج لاعب آخر للانضمام لبدء اللعبة!
        """

        await callback.answer(f"تم الانضمام كاللاعب الأول ({player1_symbol})! في انتظار اللاعب الثاني 🎮")

    else:
        # التحقق من أن اللاعب لم ينضم بالفعل
        if user_id == game_data['player1_id']:
            await callback.answer(f"أنت مشارك بالفعل في اللعبة كاللاعب الأول ({game_data['player1_symbol']})!", show_alert=True)
            return
        elif user_id == game_data['player2_id']:
            await callback.answer(f"أنت مشارك بالفعل في اللعبة كاللاعب الثاني ({game_data['player2_symbol']})!", show_alert=True)
            return

        # التحقق من حالة اللعبة
        if not game_data.get('waiting_for_second_player', False):
            await callback.answer("هذه اللعبة مكتملة بالفعل أو انتهت!", show_alert=True)
            return

        if game_data['player2_id'] is not None:
            await callback.answer("اللعبة مكتملة بالفعل مع لاعبين!", show_alert=True)
            return

        # إضافة اللاعب الثاني (O)
        games[game_owner_id][game_id]['player2_id'] = user_id
        games[game_owner_id][game_id]['player2_username'] = username
        games[game_owner_id][game_id]['waiting_for_second_player'] = False

        logger.info(f"✅ انضم اللاعب الثاني (O): {username} إلى اللعبة {game_id}")

        # تحديث نص اللعبة
        game_text = f"""
🎮 لعبة XO بدأت!

👤 اللاعب الأول: {games[game_owner_id][game_id]['player1_username']} ({games[game_owner_id][game_id]['player1_symbol']})
👤 اللاعب الثاني: {username} ({games[game_owner_id][game_id]['player2_symbol']})

⏰ دور: {games[game_owner_id][game_id]['player1_username']} ({games[game_owner_id][game_id]['player1_symbol']})
        """

        await callback.answer(f"تم الانضمام كاللاعب الثاني ({games[game_owner_id][game_id]['player2_symbol']})! بدأت اللعبة! 🎮")

    try:
        # الحصول على بيانات اللعبة المحدثة
        updated_owner_id, current_game_data = find_game_by_id(game_id)

        # إنشاء لوحة المفاتيح المناسبة
        if current_game_data.get('waiting_for_second_player', False):
            # إذا كان في انتظار اللاعب الثاني، إظهار زر الانضمام
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 انضم للعبة", callback_data=f"join_challenge_{game_id}")]
            ])
        else:
            # إذا انضم كلا اللاعبين، إظهار شبكة اللعب
            keyboard = create_game_board(current_game_data, game_id)

        # تحديث الرسالة
        if callback.message:
            await callback.message.edit_text(
                game_text.strip(),
                reply_markup=keyboard
            )
        elif callback.inline_message_id:
            await bot.edit_message_text(
                text=game_text.strip(),
                inline_message_id=callback.inline_message_id,
                reply_markup=keyboard
            )

        logger.info(f"✅ تم تحديث الرسالة بنجاح للعبة {game_id}")

    except Exception as edit_error:
        logger.error(f"❌ فشل في تحديث الرسالة: {edit_error}")
        logger.error(f"تفاصيل الخطأ: {traceback.format_exc()}")
        await callback.answer("تم قبول التحدي ولكن حدث خطأ في التحديث", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("move_"))
@safe_callback_handler
async def game_move_callback(callback: types.CallbackQuery):
    """معالج حركات اللعبة"""

    # استخراج معرف اللعبة والموضع من callback_data
    parts = callback.data.split("_")
    game_id = parts[1]
    position = int(parts[2])

    user_id = callback.from_user.id

    # البحث عن اللعبة
    game_owner_id, game_data = find_game_by_id(game_id)

    if not game_data:
        await callback.answer("لعبة غير موجودة!", show_alert=True)
        return

    if game_data['game_over']:
        await callback.answer("اللعبة انتهت!", show_alert=True)
        return

    # التحقق من أن كلا اللاعبين قد انضما
    if game_data.get('waiting_for_second_player', False):
        await callback.answer("في انتظار اللاعب الثاني للانضمام!", show_alert=True)
        return

    # تحديد دور اللاعب
    current_symbol = game_data['player1_symbol'] if game_data['current_player'] == 'X' else game_data['player2_symbol']

    # التحقق من أن اللاعب هو صاحب الدور
    if game_data['current_player'] == 'X' and user_id != game_data['player1_id']:
        await callback.answer("ليس دورك! انتظر دورك.", show_alert=True)
        return
    elif game_data['current_player'] == 'O' and user_id != game_data['player2_id']:
        await callback.answer("ليس دورك! انتظر دورك.", show_alert=True)
        return

    # التحقق من أن المربع فارغ
    if game_data['board'][position] != "":
        await callback.answer("هذا المربع مُحتل!", show_alert=True)
        return

    # إضافة الحركة
    games[game_owner_id][game_id]['board'][position] = current_symbol
    logger.info(f"تم لعب الحركة {position} بواسطة {callback.from_user.username} في اللعبة {game_id}")

    # فحص الفائز
    winner = check_winner(games[game_owner_id][game_id]['board'])
    is_full = is_board_full(games[game_owner_id][game_id]['board'])

    if winner:
        games[game_owner_id][game_id]['game_over'] = True
        games[game_owner_id][game_id]['winner'] = winner
        
        # تحديث عدد مرات الفوز
        if winner == game_data['player1_symbol']:
            games[game_owner_id][game_id]['player1_wins'] += 1
            winner_username = game_data['player1_username']
        else:
            games[game_owner_id][game_id]['player2_wins'] += 1
            winner_username = game_data['player2_username']
            
        game_text = f"""
🏆 انتهت اللعبة!

🎉 الفائز هو: {winner_username} ({winner})

📊 إحصائيات الفوز:
{game_data['player1_username']}: {games[game_owner_id][game_id]['player1_wins']} فوز/فوزات
{game_data['player2_username']}: {games[game_owner_id][game_id]['player2_wins']} فوز/فوزات
        """
    elif is_full:
        games[game_owner_id][game_id]['game_over'] = True
        game_text = f"""
🤝 انتهت اللعبة!

⚖️ النتيجة: تعادل!

📊 إحصائيات الفوز:
{game_data['player1_username']}: {games[game_owner_id][game_id]['player1_wins']} فوز/فوزات
{game_data['player2_username']}: {games[game_owner_id][game_id]['player2_wins']} فوز/فوزات
        """
    else:
        # تغيير الدور
        games[game_owner_id][game_id]['current_player'] = 'O' if game_data['current_player'] == 'X' else 'X'
        next_player = game_data['player1_username'] if games[game_owner_id][game_id]['current_player'] == 'X' else game_data['player2_username']
        next_symbol = game_data['player1_symbol'] if games[game_owner_id][game_id]['current_player'] == 'X' else game_data['player2_symbol']
        game_text = f"""
🎮 لعبة XO نشطة!

👤 اللاعب الأول: {game_data['player1_username']} ({game_data['player1_symbol']})
👤 اللاعب الثاني: {game_data['player2_username']} ({game_data['player2_symbol']})

⏰ دور: {next_player} ({next_symbol})
        """

    try:
        updated_game_data = games[game_owner_id][game_id]
        if callback.message:
            await callback.message.edit_text(
                game_text,
                reply_markup=create_game_board(updated_game_data, game_id)
            )
        elif callback.inline_message_id:
            await bot.edit_message_text(
                text=game_text,
                inline_message_id=callback.inline_message_id,
                reply_markup=create_game_board(updated_game_data, game_id)
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"خطأ في تحديث الرسالة: {e}")
        await callback.answer("تم تسجيل الحركة ولكن حدث خطأ في التحديث")

@dp.callback_query(lambda c: c.data == "back_to_main")
@safe_callback_handler
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """معالج زر العودة للقائمة الرئيسية"""
    await state.set_state(XOStates.main_menu)
    welcome_text = """
🎯 مرحباً بك في عالم لعبة XO المثيرة!

⚡ اختبر مهاراتك في أشهر لعبة استراتيجية
🏆 تحدَّ أصدقاءك واستمتع بالمنافسة
🎮 لعبة سريعة ومسلية في أي وقت

ماذا تريد أن تفعل؟
    """
    await callback.message.edit_text(
        welcome_text,
        reply_markup=create_main_menu_keyboard()
    )
    await callback.answer("تم العودة للقائمة الرئيسية")

@dp.callback_query(lambda c: c.data.startswith("delete"))
@safe_callback_handler
async def delete_game_callback(callback: types.CallbackQuery):
    """معالج زر حذف اللعبة"""

    # استخراج معرف اللعبة من callback_data
    game_id = callback.data.split("_")[1]

    # البحث عن اللعبة وحذفها
    game_owner_id, game_data = find_game_by_id(game_id)

    if game_data:
        del games[game_owner_id][game_id]
        logger.info(f"تم حذف اللعبة {game_id} من المستخدم {game_owner_id}")

        # إذا لم تعد هناك ألعاب لهذا المستخدم، احذف مدخل المستخدم
        if not games[game_owner_id]:
            del games[game_owner_id]
            logger.info(f"تم حذف مدخل المستخدم {game_owner_id} لعدم وجود ألعاب")

        delete_text = """
🗑️ تم حذف اللعبة بنجاح!

✨ يمكنك بدء تحدي جديد في أي وقت
🎮 اضغط على الزر أدناه لإنشاء لعبة جديدة

🔥 هل أنت مستعد للمزيد من التحدي؟
        """

        delete_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ابدأ تحدي جديد!", callback_data="start_challenge")]
        ])

        try:
            if callback.message:
                await callback.message.edit_text(
                    delete_text,
                    reply_markup=delete_keyboard
                )
            elif callback.inline_message_id:
                await bot.edit_message_text(
                    text=delete_text,
                    inline_message_id=callback.inline_message_id,
                    reply_markup=delete_keyboard
                )
            await callback.answer("تم حذف اللعبة بنجاح! 🗑️")
        except Exception as e:
            logger.error(f"خطأ في حذف اللعبة: {e}")
            await callback.answer("تم حذف اللعبة")
    else:
        await callback.answer("اللعبة غير موجودة أو تم حذفها بالفعل!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("reset"))
@safe_callback_handler
async def reset_game_callback(callback: types.CallbackQuery):
    """معالج زر إعادة اللعبة مع تبديل الأدوار"""

    # استخراج معرف اللعبة من callback_data
    game_id = callback.data.split("_")[1]

    # البحث عن اللعبة
    game_owner_id, old_game_data = find_game_by_id(game_id)

    if not old_game_data:
        await callback.answer("اللعبة غير موجودة!", show_alert=True)
        return

    # حفظ إحصائيات الفوز
    player1_wins = old_game_data.get('player1_wins', 0)
    player2_wins = old_game_data.get('player2_wins', 0)

    # إنشاء لعبة جديدة مع تبديل الأدوار
    if old_game_data.get('player1_id') and old_game_data.get('player2_id'):
        # تبديل الأدوار: اللاعب الثاني يصبح الأول والأول يصبح الثاني
        games[game_owner_id][game_id] = {
            'board': [""] * 9,
            'current_player': 'X',
            'player1_id': old_game_data['player2_id'],      # اللاعب الثاني السابق يصبح الأول
            'player2_id': old_game_data['player1_id'],      # اللاعب الأول السابق يصبح الثاني
            'player1_username': old_game_data['player2_username'],  # تبديل الأسماء
            'player2_username': old_game_data['player1_username'],
            'player1_symbol': old_game_data['player2_symbol'],  # تبديل الرموز
            'player2_symbol': old_game_data['player1_symbol'],
            'game_over': False,
            'winner': None,
            'waiting_for_second_player': False,
            'player1_wins': player1_wins,  # الاحتفاظ بعدد مرات الفوز
            'player2_wins': player2_wins
        }

        # رسالة اللعبة الجديدة مع الأدوار المبدلة
        reset_text = f"""
🔄 تم إعادة اللعبة مع تبديل الأدوار!

👤 اللاعب الأول: {games[game_owner_id][game_id]['player1_username']} ({games[game_owner_id][game_id]['player1_symbol']})
👤 اللاعب الثاني: {games[game_owner_id][game_id]['player2_username']} ({games[game_owner_id][game_id]['player2_symbol']})

⏰ دور: {games[game_owner_id][game_id]['player1_username']} ({games[game_owner_id][game_id]['player1_symbol']})

📊 إحصائيات الفوز:
{games[game_owner_id][game_id]['player1_username']}: {player2_wins} فوز/فوزات
{games[game_owner_id][game_id]['player2_username']}: {player1_wins} فوز/فوزات
        """

        reset_keyboard = create_game_board(games[game_owner_id][game_id], game_id)
        logger.info(f"تم إنشاء لعبة جديدة مع تبديل الأدوار للمستخدم {game_owner_id} واللعبة {game_id}")

    else:
        # إذا لم تكن هناك بيانات كافية، العودة لرسالة التحدي العادية
        reset_text = """
🎯 تحدي XO جديد وحماسي!

🔥 هل أنت مستعد لجولة جديدة؟
⚡ لعبة سريعة ومثيرة تنتظرك!
🏆 من سيكون بطل هذه المرة؟

👇 اقبل التحدي وابدأ المعركة!
        """
        reset_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 اقبل التحدي الجديد!", callback_data=f"join_challenge_{game_id}")]
        ])

    try:
        if callback.message:
            await callback.message.edit_text(
                reset_text,
                reply_markup=reset_keyboard
            )
        elif callback.inline_message_id:
            await bot.edit_message_text(
                text=reset_text,
                inline_message_id=callback.inline_message_id,
                reply_markup=reset_keyboard
            )
        await callback.answer("تم إعادة تعيين اللعبة مع تبديل الأدوار! 🔄")
    except Exception as e:
        logger.error(f"خطأ في إعادة تعيين اللعبة: {e}")
        await callback.answer("تم إعادة تعيين اللعبة")

# === معالج الاستعلامات المضمنة ===

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery, state: FSMContext):
    """معالج الاستعلامات المضمنة"""
    try:
        logger.info(f"استعلام مضمن من {inline_query.from_user.username}: {inline_query.query}")

        if inline_query.query.strip() == "play_xo":
            # إنشاء معرف فريد للعبة
            game_id = create_unique_game_id()

            # استرجاع بيانات الرموز من حالة المستخدم
            user_data = await state.get_data()
            player1_symbol = user_data.get('player1_symbol', '❌')
            player2_symbol = user_data.get('player2_symbol', '⭕')
            
            # إنشاء نتيجة واحدة للتحدي
            result = InlineQueryResultArticle(
                id="1",
                title="🎮 تحدي XO مثير!",
                description="ابدأ منافسة ممتعة مع أصدقائك الآن",
                input_message_content=InputTextMessageContent(
                    message_text=f"""
🎯 تحدي XO حماسي!

🔥 هل أنت مستعد لإثبات مهاراتك؟
⚡ لعبة سريعة ومثيرة تنتظرك!
🏆 من سيكون بطل هذه الجولة؟

الرموز المستخدمة:
اللاعب الأول: {player1_symbol}
اللاعب الثاني: {player2_symbol}

👇 اقبل التحدي وابدأ المعركة!
                    """
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎮 اقبل التحدي!", callback_data=f"join_challenge_{game_id}")]
                ])
            )

            await inline_query.answer([result], cache_time=0)
            logger.info("تم إرسال نتيجة الاستعلام المضمن بنجاح")

    except Exception as e:
        logger.error(f"خطأ في معالج الاستعلام المضمن: {e}")
        logger.error(traceback.format_exc())

# === إعدادات الخادم للتشغيل المستمر ===

# متغير لتتبع حالة البوت
bot_status = {
    'start_time': None,
    'last_heartbeat': None,
    'total_users': 0,
    'active_games': 0,
    'uptime': '0 days, 0 hours, 0 minutes'
}

def update_bot_stats():
    """تحديث إحصائيات البوت"""
    if bot_status['start_time']:
        uptime_seconds = time.time() - bot_status['start_time']
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        bot_status['uptime'] = f"{days} days, {hours} hours, {minutes} minutes"

    bot_status['last_heartbeat'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    bot_status['active_games'] = sum(len(user_games) for user_games in games.values())

async def web_handler(request):
    """معالج طلبات الويب للحفاظ على نشاط البوت مع معلومات مفصلة"""
    update_bot_stats()

    status_html = f"""
    <!DOCTYPE html>
    <html dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 حالة بوت XO</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                margin: 0;
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 30px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }}
            .status-card {{
                background: rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                padding: 20px;
                margin: 15px 0;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            .status-indicator {{
                display: inline-block;
                width: 12px;
                height: 12px;
                background: #00ff00;
                border-radius: 50%;
                animation: pulse 2s infinite;
                margin-left: 10px;
            }}
            @keyframes pulse {{
                0% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
                100% {{ opacity: 1; }}
            }}
            h1 {{ text-align: center; margin-bottom: 30px; }}
            h2 {{ color: #ffd700; }}
            .metric {{ margin: 10px 0; font-size: 16px; }}
            .refresh-btn {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px 5px;
            }}
            .refresh-btn:hover {{ background: #45a049; }}
        </style>
        <script>
            function refreshPage() {{ location.reload(); }}
            setInterval(refreshPage, 30000); // تحديث كل 30 ثانية
        </script>
    </head>
    <body>
        <div class="container">
            <h1>🤖 بوت XO - لوحة المراقبة</h1>

            <div class="status-card">
                <h2>🟢 حالة البوت <span class="status-indicator"></span></h2>
                <div class="metric">📊 الحالة: <strong>يعمل بشكل طبيعي</strong></div>
                <div class="metric">⏰ آخر نبضة: <strong>{bot_status['last_heartbeat']}</strong></div>
                <div class="metric">🕐 وقت التشغيل: <strong>{bot_status['uptime']}</strong></div>
            </div>

            <div class="status-card">
                <h2>📈 الإحصائيات</h2>
                <div class="metric">🎮 الألعاب النشطة: <strong>{bot_status['active_games']}</strong></div>
                <div class="metric">💾 استخدام الذاكرة: <strong>{len(games)} مستخدم مُخزن</strong></div>
                <div class="metric">🔄 إجمالي الألعاب: <strong>{sum(len(user_games) for user_games in games.values())} لعبة مُسجلة</strong></div>
            </div>

            <div class="status-card">
                <h2>ℹ️ معلومات النظام</h2>
                <div class="metric">🌐 المنفذ: <strong>{PORT}</strong></div>
                <div class="metric">📡 نوع الاتصال: <strong>Webhook + Polling</strong></div>
                <div class="metric">🔐 الحماية: <strong>مُفعلة</strong></div>
                <div class="metric">🔄 التحديث التلقائي: <strong>كل 30 ثانية</strong></div>
            </div>

            <div style="text-align: center; margin-top: 20px;">
                <button class="refresh-btn" onclick="refreshPage()">🔄 تحديث يدوي</button>
                <button class="refresh-btn" onclick="window.open('/health', '_blank')">📊 فحص الصحة</button>
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=status_html, content_type='text/html')

async def health_check_handler(request):
    """معالج فحص صحة البوت"""
    update_bot_stats()

    health_data = {
        "status": "healthy",
        "timestamp": bot_status['last_heartbeat'],
        "uptime": bot_status['uptime'],
        "active_games": bot_status['active_games'],
        "memory_usage": len(games),
        "bot_responsive": True
    }

    return web.json_response(health_data)

async def ping_handler(request):
    """معالج ping بسيط"""
    return web.Response(text="pong! 🏓")

# === معالج الأخطاء العام ===

@dp.error()
async def error_handler(event, exception):
    """معالج عام للأخطاء"""
    logger.error(f"خطأ غير متوقع: {exception}")
    logger.error(traceback.format_exc())
    return True

# === الدالة الرئيسية ===

async def start_web_server():
    """بدء تشغيل خادم الويب"""
    app = web.Application()
    app.router.add_get('/', web_handler)
    app.router.add_get('/health', health_check_handler)
    app.router.add_get('/ping', ping_handler)
    app.router.add_get('/status', web_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    bot_status['start_time'] = time.time()
    logger.info(f"🌐 خادم الويب يعمل على المنفذ {PORT}")
    return runner

async def main():
    """الدالة الرئيسية لتشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
    # بدء خادم الويب
    web_runner = await start_web_server()
    
    # بدء استقبال التحديثات
    await dp.start_polling(bot)
    
    # تنظيف بعد التوقف
    await bot.session.close()
    await web_runner.cleanup()
    logger.info("🔚 تم إيقاف البوت")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ تم إيقاف البوت بواسطة المستخدم")
    except Exception as e:
        logger.error(f"💥 خطأ في تشغيل البوت: {e}")
        logger.error(traceback.format_exc())
