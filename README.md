# 51-BYPASS (`51b`)

**51-BYPASS** — автономный инструмент и шлюз для автоматического обхода региональных ограничений (**HTTP 451** / **HTTP 403**) для AI API на базе Cloudflare Workers:
- **NVIDIA NIM API** (`integrate.api.nvidia.com`, `api.ngc.nvidia.com`, `build.nvidia.com`) — 100% обход ошибки 451.
- **OpenAI / ChatGPT API** (`api.openai.com`) — обход регионального блока 403.
- **xAI Grok API** (`api.x.ai`) — обход регионального блока 403.
- **Anthropic, Groq, Perplexity, ElevenLabs, OpenRouter** и любые пользовательские домены.

---

## ⚡ Установка в 1 клик (PowerShell)

Откройте PowerShell и выполните:

```powershell
irm https://raw.githubusercontent.com/username/51-bypass/main/install.ps1 | iex
```

*(или просто скачайте репозиторий и дважды кликните на `setup.bat`)*.

Установщик:
1. Проверит окружение Windows и Python 3.
2. Скопирует файлы в `%LOCALAPPDATA%\51-bypass`.
3. Добавит команду **`51b`** в системный `PATH` пользователя.
4. Автоматически подключит Cloudflare (или подтянет существующие ключи), настроит маршрут `*.workers.dev` и задеплоит воркер.
5. Зарегистрирует ежедневную фоновую службу синхронизации в Планировщике Windows.
6. Выполнит полную диагностику системы.

---

## 🚀 Использование CLI (`51b`)

После установки команда **`51b`** доступна из любого терминала (PowerShell, CMD, терминал VS Code, Cursor).

### 1. Интерактивная консоль
Запустите `51b` без параметров:

```text
===============================================================
     51-BYPASS v1.0.0 -- AI Gateway & Regional Restriction Bypass
===============================================================
  Active Domains: 14 (14 core, 0 custom)
  Gateway URL:    https://ai-gateway.whyx1ere.workers.dev
---------------------------------------------------------------
  [1] Check Service     - Verify Gateway, Worker, and Task health
  [2] Test Domains      - Probe active endpoints for 451/403 bypass
  [3] Update Domains    - Check and pull latest domains from GitHub
  [4] Import Domains    - Edit personal custom domains in Notepad
  [5] Run Diagnostics   - Full 8-point system diagnostics
  [0] Exit
===============================================================
```

### 2. Команды для терминала и скриптов

```cmd
:: Проверить обход 451 на NVIDIA NIM
51b test integrate.api.nvidia.com

:: Проверить состояние службы и шлюза
51b check-service

:: Обновить основные домены из GitHub-репозитория
51b update

:: Показать все активные домены (core и пользовательские)
51b domains list

:: Добавить личный домен (сохраняется в отдельном user_domains.txt)
51b domains add api.my-custom-service.com

:: Удалить личный домен
51b domains remove api.my-custom-service.com

:: Открыть Notepad для редактирования личных доменов
51b import

:: Управление списками и пресетами
51b lists
51b lists create "My AI Tools" --desc "Кастомный список"
51b lists add-domain my-ai-tools api.perplexity.ai
51b lists show my-ai-tools

:: Интерактивный импорт доменов через Блокнот
51b import

:: Экспорт и импорт списков в текстовый файл
51b lists export my-ai-tools domains.txt
51b lists import my-ai-tools domains.txt

:: Запустить полную диагностику системы
51b diagnostics

:: Принудительно залить изменения на Cloudflare
51b sync

:: Управление фоновой службой синхронизации
51b service status
51b service install
51b service uninstall
```

---

## 💻 Использование в коде (Python / LangChain / Cursor)

### Режим Drop-In (дефолтный адрес)
По умолчанию запросы на `/v1/...` автоматически направляются на NVIDIA NIM:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/v1",
    api_key="nvapi-..."  # ваш ключ NVIDIA API
)

response = client.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    messages=[{"role": "user", "content": "Привет! Обход работает?"}]
)
print(response.choices[0].message.content)
```

### Режим Multi-Domain (для любого сервиса в одном шлюзе)
```python
# OpenAI
client = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.openai.com/v1",
    api_key="sk-..."
)

# xAI Grok
client = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.x.ai/v1",
    api_key="xai-..."
)
```

---

## 🛡 Архитектура и надежность

1. **Никакого VPN и перехвата системного трафика:** Игры, банки, Telegram и браузер работают на максимальной чистой скорости вашего провайдера.
2. **ES Module Cloudflare Worker:**
   - Поддерживает Token Streaming / SSE (`text/event-stream`) в реальном времени.
   - Очищает заголовки `content-encoding` и `transfer-encoding`, предотвращая сбои распаковки в Python (`httpx`, `requests`).
   - Подменяет гео-заголовки `x-forwarded-for` и `x-real-ip` на зарубежные IP Cloudflare.
3. **Безопасное хранение:** Конфигурация пишется атомарно в `~/.51-bypass/config.json` с автосозданием резервной копии `.bak`. Токены никогда не выводятся в открытом виде.
