# 451bypass (`451b`)

**451bypass** — автономный инструмент и шлюз для автоматического обхода региональных ограничений (**HTTP 451** / **HTTP 403**) для AI API на базе Cloudflare Workers:
- **NVIDIA NIM API** (`integrate.api.nvidia.com`, `api.ngc.nvidia.com`, `build.nvidia.com`) — 100% обход ошибки 451.
- **OpenAI / ChatGPT API** (`api.openai.com`) — обход регионального блока 403.
- **xAI Grok API** (`api.x.ai`) — обход регионального блока 403.
- **Anthropic, Groq, Perplexity, ElevenLabs, OpenRouter, DeepSeek, Mistral** и любые пользовательские домены.

---

## ⚡ Установка в 1 клик (PowerShell)

Откройте PowerShell и выполните:

```powershell
irm https://raw.githubusercontent.com/nebylotech/451bypass/main/install.ps1 | iex
```

*(или просто скачайте репозиторий и дважды кликните на `setup.bat`)*.

Установщик:
1. Проверит окружение Windows и Python 3.
2. Скопирует файлы в `%LOCALAPPDATA%\451bypass`.
3. Добавит команду **`451b`** (и алиасы `451bypass`, `51b`) в системный `PATH` пользователя.
4. Автоматически подключит Cloudflare (или подтянет существующие ключи), настроит маршрут `*.workers.dev` и задеплоит воркер.
5. Зарегистрирует ежедневную фоновую службу синхронизации в Планировщике Windows.
6. Выполнит полную диагностику системы.

---

## 🚀 Использование CLI (`451b` / `451bypass`)

После установки команда **`451b`** доступна из любого терминала (PowerShell, CMD, терминал VS Code, Cursor).

### 1. Интерактивная консоль
Запустите `451b` без параметров:

```text
===============================================================
     451bypass v1.0.0 -- AI Gateway & Regional Restriction Bypass
===============================================================
  Active Domains: 13 (13 core, 0 custom)
  Gateway URL:    https://ai-gateway.whyx1ere.workers.dev
---------------------------------------------------------------
  [1] Check Service     - Verify Gateway, Worker, and Task health
  [2] Test Domains      - Probe active endpoints for 451/403 bypass
  [3] Update Domains    - Check and pull latest domains from GitHub
  [4] Custom Domains    - Edit personal custom.txt in Notepad (auto-sync)
  [5] Run Diagnostics   - Full 8-point system diagnostics
  [0] Exit
===============================================================
```

### 2. Команды для терминала и скриптов

```cmd
:: Проверить обход 451 на NVIDIA NIM
451b test integrate.api.nvidia.com

:: Проверить состояние службы и шлюза
451b check-service

:: Обновить основные домены из GitHub-репозитория
451b update

:: Показать все активные домены (core и пользовательские)
451b domains list

:: Добавить личный домен (сохраняется в custom.txt)
451b domains add api.my-custom-service.com

:: Удалить личный домен
451b domains remove api.my-custom-service.com

:: Открыть Notepad для редактирования личных доменов (с авто-удалением дубликатов)
451b import

:: Запустить полную диагностику системы
451b diagnostics

:: Принудительно залить изменения на Cloudflare
451b sync

:: Управление фоновой службой синхронизации
451b service status
451b service install
451b service uninstall
```

---

## 💻 Использование в коде (Python / LangChain / Cursor)

### Режим Multi-Domain (для любого сервиса в одном шлюзе)
```python
from openai import OpenAI

# OpenAI через 451bypass
client = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.openai.com/v1",
    api_key="sk-..."
)

# NVIDIA NIM через 451bypass
client_nvidia = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/integrate.api.nvidia.com/v1",
    api_key="nvapi-..."
)

# xAI Grok через 451bypass
client_grok = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.x.ai/v1",
    api_key="xai-..."
)
```

---

## 🛡 Архитектура и надежность

1. **Никакого VPN и перехвата системного трафика:** Игры, банки, Telegram и браузер работают на максимальной чистой скорости вашего провайдера.
2. **Динамический ES Module Cloudflare Worker:**
   * Базовые домены динамически подтягиваются с GitHub Raw и кэшируются на узлах Cloudflare Edge.
   * Поддерживает Token Streaming / SSE (`text/event-stream`) в реальном времени.
   * Очищает заголовки `content-encoding` и `transfer-encoding`, предотвращая сбои распаковки в Python (`httpx`, `requests`).
   * Подменяет гео-заголовки `x-forwarded-for` и `x-real-ip` на зарубежные IP Cloudflare.
3. **Умное отслеживание `custom.txt`:** Автоматически сверяет кастомные домены с `core.txt` на воркере, очищает дубликаты и выгружает обновленный список на воркер.
4. **Безопасное хранение:** Конфигурация пишется атомарно в `%LOCALAPPDATA%\451bypass\config.json` с автосозданием резервной копии `.bak`. Токены никогда не выводятся в открытом виде.
