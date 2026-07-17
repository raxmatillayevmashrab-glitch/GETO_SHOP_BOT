"""
Bu fayl config.py o'rniga ishlatiladi — tokenni faylga yozib qo'yish o'rniga,
Railway'ning "Variables" bo'limidan o'qiydi. Shunday qilib token GitHub'ga
(hatto Private repo bo'lsa ham) hech qachon tushmaydi.

RAILWAY'DA SOZLASH:
    Project -> Variables -> quyidagilarni qo'shing:
        BOT_TOKEN = sizning tokeningiz
        ADMIN_ID  = sizning Telegram ID raqamingiz
"""

import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

CLICK_PAY_LINK_TEMPLATE = os.environ.get(
    "CLICK_PAY_LINK_TEMPLATE",
    "https://my.click.uz/services/pay?service_id=SIZNING_SERVICE_ID"
    "&merchant_id=SIZNING_MERCHANT_ID&amount={amount}&transaction_param={order_id}",
)
PAYME_PAY_LINK_TEMPLATE = os.environ.get(
    "PAYME_PAY_LINK_TEMPLATE",
    "https://checkout.paycom.uz/DEMO_BASE64_BUYERGA_MERCHANT_ID_AMOUNT_ORDERID_KODLANADI"
    "?order={order_id}&amount={amount}",
)
