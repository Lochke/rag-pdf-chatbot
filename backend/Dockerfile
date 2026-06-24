FROM python:3.12-slim

WORKDIR /app

# Cài dependencies trước để tận dụng Docker layer cache
# (nếu chỉ sửa code, không sửa requirements.txt, build lại sẽ nhanh hơn)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
