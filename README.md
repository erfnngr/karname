# کارنامه (Karname Desktop)

نرم‌افزار دسکتاپ یکپارچه کارنامه (PySide6 + React/TypeScript/Tailwind + QtWebEngine).

## ساختار پوشه‌ها
- ریشه پروژه: کدهای Python / PySide6، تست‌ها (	ests/)، فایل‌های داده و باندل آماده رابط کاربری (web/react-design/)
- rontend/: سورس کامل رابط کاربری React + TypeScript + Tailwind + Vite

## اجرای توسعه (Development)
1. نصب وابستگی‌های پایتون:
   ``bash
   pip install -r requirements.txt
   ``
2. (اختیاری، هنگام ویرایش رابط React) بیلد رابط کاربری و همگام‌سازی با web/react-design:
   ``bash
   cd frontend
   npm install
   npx vite build
   ``
   سپس محتوای rontend/dist را در web/react-design کپی کنید.
3. اجرای برنامه:
   ``bash
   python launcher.py
   ``

## ساخت فایل اجرایی ویندوز
``bash
pyinstaller --distpath dist-react --noconfirm --clean Karname.spec
``
