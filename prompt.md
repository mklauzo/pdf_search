# Prompt: Web aplikacja do przeszukiwania PDF (Docker + OCR)

Jesteś doświadczonym full-stack developerem oraz DevOps engineerem.

Twoim zadaniem jest zbudowanie kompletnej aplikacji webowej uruchamianej w Dockerze, która umożliwia przeszukiwanie lokalnych plików PDF.

---

## 🎯 Cel

Stworzyć aplikację web, która:

- pozwala wskazać katalog z PDF z hosta
- obsługuje PDF tekstowe oraz skany
- umożliwia wyszukiwanie fraz
- zwraca nazwę pliku, numer strony i fragment kontekstu
- działa w całości w Dockerze

---

## ✅ Wymagania funkcjonalne

### 1. Źródło plików

Aplikacja ma korzystać z katalogu podmontowanego jako volume Dockera:

/data


To tam znajdują się pliki PDF.

---

### 2. Obsługiwane typy PDF

- PDF wektorowe (tekstowe)
- PDF bitmapowe (skany – wymagany OCR)

---

### 3. UI

Użytkownik w interfejsie:

- wpisuje frazę
- widzi tabelę wyników

---

### 4. Wyniki wyszukiwania

Każdy wynik zawiera:

- nazwę pliku
- numer strony
- fragment tekstu (~150–300 znaków)
- podświetloną frazę

---

### 5. OCR

Dla PDF bitmapowych:

- użyj Tesseract
- język: polski
- wynik OCR zapisz w cache (SQLite lub pliki lokalne)
- OCR nie może być wykonywany ponownie dla tego samego pliku

---

## 🧠 Backend

Technologie:

- Python
- FastAPI
- pdfplumber lub PyMuPDF (PDF tekstowe)
- pytesseract + pdf2image (skany)
- SQLite jako lokalny indeks

---

### Endpoint API



POST /search


Body:

```json
{
  "query": "szukany tekst"
}


Response:

[
  {
    "file": "example.pdf",
    "page": 4,
    "snippet": "...tekst z kontekstem..."
  }
]

Dodatkowe funkcje

automatyczna indeksacja PDF przy starcie

zapis indeksu w SQLite

wyszukiwanie realizowane przez SQL LIKE lub FTS5

przycisk „Reindex”

progres indeksowania

🖥 Frontend

Możliwe opcje:

prosty HTML + JS
lub

React + Vite

UI:

input do wpisania frazy

przycisk search

tabela wyników

🐳 Docker

Przygotuj:

Dockerfile

docker-compose.yml

Kontener musi:

instalować tesseract + język polski

montować katalog hosta jako /data

expose port 8000

Przykład uruchomienia:

docker compose up --build

📁 Struktura projektu

Ma być czytelna, np:

app/
  backend/
  frontend/
docker-compose.yml
Dockerfile
README.md

📄 README.md

Ma zawierać:

wymagania

instrukcję uruchomienia

przykład montowania katalogu PDF

opis API

📦 Wynik

Wygeneruj:

pełne źródła projektu

Dockerfile

docker-compose.yml

README.md

Kod ma być produkcyjnej jakości.
