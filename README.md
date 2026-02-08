# PDF Search

Aplikacja webowa do przeszukiwania lokalnych plików PDF (tekstowych i skanów) z obsługą OCR.

## Funkcje

- Pełnotekstowe wyszukiwanie w plikach PDF (SQLite FTS5)
- Automatyczny OCR skanów przez Tesseract (język polski)
- Inteligentna detekcja — decyzja tekst vs OCR na poziomie strony
- Cache indeksu na podstawie SHA-256 — niezmienione pliki nie są reindeksowane
- Prosty interfejs webowy z podświetlaniem fraz w wynikach
- Pasek postępu indeksowania w czasie rzeczywistym
- Wybór podkatalogu do indeksowania z poziomu przeglądarki
- Podgląd wyrenderowanych stron PDF w wynikach wyszukiwania

## Wymagania

- Docker i Docker Compose

## Uruchomienie

1. Uruchom kontener, wskazując katalog z PDF-ami:

```bash
PDF_DIR=~/dokumenty docker compose up --build
```

Bez ustawienia `PDF_DIR` używany jest domyślny katalog `./data/`.

2. Otwórz przeglądarkę: http://localhost:8000

Pliki PDF zostaną automatycznie zaindeksowane przy starcie.

Można też ustawić zmienną na stałe w pliku `.env` obok `docker-compose.yml`:

```
PDF_DIR=/home/jan/dokumenty
```

## Wybór katalogu

W interfejsie webowym nad polem wyszukiwania wyświetlany jest aktualnie indeksowany katalog. Za pomocą listy rozwijanej można wybrać podkatalog `/data` — po zmianie indeks jest czyszczony i pliki z nowego katalogu są automatycznie indeksowane.

## API

| Metoda | Endpoint              | Opis                                         |
|--------|-----------------------|----------------------------------------------|
| POST   | `/search`             | Wyszukiwanie: `{"query": "tekst"}`           |
| POST   | `/reindex`            | Reindeksacja wszystkich plików               |
| GET    | `/indexing-status`    | Status indeksowania (JSON)                   |
| GET    | `/current-directory`  | Aktualnie wybrany katalog                    |
| GET    | `/directories`        | Lista podkatalogów `/data` (max 2 poziomy)   |
| POST   | `/set-directory`      | Zmiana katalogu: `{"path": "subdir"}`        |
| GET    | `/page-image`         | Obraz strony PDF: `?file=nazwa.pdf&page=1`   |

## Struktura projektu

```
app/
  backend/
    main.py       - FastAPI, endpointy, startup
    indexer.py     - przetwarzanie PDF, OCR, indeksowanie
    database.py    - SQLite/FTS5 schemat i zapytania
  frontend/
    index.html    - interfejs webowy
Dockerfile
docker-compose.yml
requirements.txt
```
