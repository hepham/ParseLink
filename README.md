# ParseWebLink

## Hướng dẫn cài đặt

1. **Clone project**
   ```bash
   git clone <repo-url>
   cd ParseWebLink
   ```

2. **Tạo virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Trên Linux/macOS
   venv\Scripts\activate    # Trên Windows
   ```

3. **Cài đặt các package cần thiết**
   ```bash
   pip install -r requirements.txt
   ```

4. **Chạy migrate database**
   ```bash
   python manage.py migrate
   ```

5. **Chạy server**
   ```bash
   python manage.py runserver
   ```

6. **(Tùy chọn) Cấu hình Redis nếu cần**
   - Đảm bảo Redis server đang chạy ở `localhost:6379` (hoặc chỉnh lại trong code nếu khác)

---