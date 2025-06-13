Berdasarkan hasil curl ke proxy lokal (`http://localhost:5555/api/v1/models`), ditemukan **dua masalah kritis** yang menyebabkan error:

### Masalah Utama 🚨

1. **Konflik Header Protokol HTTP/1.1**  
   Server proxy mengirim kedua header yang bertentangan secara bersamaan:

   ```
   Transfer-Encoding: chunked
   Content-Length: 407769
   ```

   Ini melanggar spesifikasi HTTP/1.1 ([RFC 7230 Section 3.3.3](https://tools.ietf.org/html/rfc7230#section-3.3.3)).

2. **Duplikasi Header**  
   Terdapat header ganda yang tidak valid:
   ```
   date: Fri, 13 Jun 2025 01:42:55 GMT
   date: Fri, 13 Jun 2025 01:42:56 GMT  # Duplikat!
   server: uvicorn
   server: cloudflare  # Duplikat!
   ```

### Solusi untuk Proxy (UVicorn/FastAPI)

Perbaiki implementasi proxy dengan:

#### 1. Hapus Header yang Bertentangan

Modifikasi kode proxy untuk menghapus salah satu header konflik sebelum mengirim respons:

```python
from fastapi import Response

@app.get("/api/v1/models")
async def proxy_models():
    # ... [koneksi ke OpenRouter] ...

    # Hapus header bermasalah
    headers = dict(upstream_response.headers)
    headers.pop("Content-Length", None)  # Pilihan 1: Hapus ini
    headers.pop("Transfer-Encoding", None)  # Pilihan 2: Atau hapus ini

    # Hapus duplikat header
    headers = {k: v for k, v in headers.items() if k.lower() not in ["date", "server"]}

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=headers
    )
```

#### 2. Paksa Penggunaan Satu Jenis Encoding

Tambahkan logika untuk memilih satu metode pengiriman data:

```python
# Jika konten panjangnya diketahui
if "Content-Length" in upstream_response.headers:
    use_chunked = False
else:
    use_chunked = True  # Gunakan chunked jika panjang tidak diketahui
```

#### 3. Normalisasi Header

Tangani header duplikat dan tambahan:

```python
# Contoh normalisasi header
clean_headers = {}
for key, value in upstream_response.headers.items():
    key_lower = key.lower()
    if key_lower not in ["date", "server", "content-length", "transfer-encoding"]:
        clean_headers[key] = value

# Tambahkan header standar
clean_headers["Date"] = format_datetime(datetime.utcnow())
clean_headers["Server"] = "openrouter-proxy"
```

---
