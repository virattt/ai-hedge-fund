# Hướng Dẫn Sử Dụng AI Hedge Fund

Tài liệu này giải thích cách cài đặt và chạy dự án **AI Hedge Fund** bằng tiếng Việt. Mục tiêu của tài liệu là giúp người mới không rành code vẫn có thể sử dụng hệ thống.

## 1. Giới Thiệu Nhanh

AI Hedge Fund là một dự án minh hoạ việc dùng trí tuệ nhân tạo để đưa ra quyết định giao dịch. Phần mềm chỉ dành cho **mục đích học tập và nghiên cứu**, không phải để đầu tư thật. Tác giả không chịu trách nhiệm về bất kỳ rủi ro tài chính nào.

## 2. Chuẩn Bị Môi Trường

- Máy tính cần cài sẵn **Python 3**, **Git** và **Poetry**.
- Nếu muốn chạy giao diện web (frontend), bạn cần cài thêm **Node.js**.
- Với người dùng Windows, dùng file `run.bat`.
- Với người dùng Mac/Linux, dùng file `run.sh`.

## 3. Tải Mã Nguồn

Mở cửa sổ dòng lệnh và chạy:

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
```

## 4. Tạo File Cấu Hình `.env`

Sao chép file mẫu và chỉnh sửa để thêm các khoá API của bạn:

```bash
cp .env.example .env
```

Mở file `.env` và điền các khoá như `OPENAI_API_KEY`, `GROQ_API_KEY`, `FINANCIAL_DATASETS_API_KEY` (nếu có). Đây là các khoá dùng để gọi mô hình AI và lấy dữ liệu thị trường.

## 5. Cách Chạy Nhanh

### Trên Mac/Linux

```bash
./run.sh
```

Nếu gặp lỗi không có quyền chạy, hãy chạy lệnh sau rồi thử lại:

```bash
chmod +x run.sh && ./run.sh
```

### Trên Windows

Mở Command Prompt và chạy:

```cmd
run.bat
```

Script sẽ tự động cài các phụ thuộc cần thiết và khởi động dịch vụ. Khi chạy xong, bạn có thể mở trình duyệt tới địa chỉ `http://localhost:5173` để xem giao diện (nếu sử dụng phiên bản có frontend) hoặc theo dõi kết quả ở màn hình dòng lệnh.

## 6. Tuỳ Chọn Giao Dịch Crypto

Nếu muốn bật chế độ giao dịch tiền mã hoá, đặt biến môi trường `ASSET_CLASS=CRYPTO` trước khi chạy. Ví dụ:

```bash
ASSET_CLASS=CRYPTO ./run.sh --ticker BTC/USDT --exchange binance
```

## 7. Chạy Thủ Công Bằng Poetry (Tuỳ Chọn)

Người dùng có kinh nghiệm hơn có thể chạy trực tiếp bằng Poetry:

```bash
poetry install
poetry run python src/main.py --tickers AAPL,MSFT,NVDA
```

Có thể thêm các tuỳ chọn `--start-date`, `--end-date`, `--show-reasoning` hoặc `--ollama` để dùng mô hình LLM cục bộ.

## 8. Lưu Ý Quan Trọng

- Phần mềm này chỉ phục vụ **mục đích học tập**.
- Không nên dùng để giao dịch với tiền thật.
- Kết quả trong quá khứ không đảm bảo cho tương lai.
- Tác giả không chịu trách nhiệm cho bất kỳ khoản lỗ nào.

Chúc bạn thành công trong quá trình khám phá dự án!

