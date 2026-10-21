# 🚀 451bypass (`451b`)

<p align="center">
  <b>⚡ Персональный AI-шлюз и локальный маршрутизатор для мгновенного обхода блокировок HTTP 451 и 403</b><br>
  <i>Без падения скорости интернета, без медленных VPN, без абонентской платы и без рекламы.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?style=for-the-badge&logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.8+-yellow?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Cloudflare-Zero--Cost-orange?style=for-the-badge&logo=cloudflare" alt="Cloudflare">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

---

## 💡 В чём проблема с обычными VPN?

* ❌ **Режут скорость:** торренты, загрузки, онлайн-игры и стримы начинают лагать.
* ❌ **Ломают сервисы:** банки, Госуслуги, такси и локальные сайты блокируют иностранные VPN IP.
* ❌ **Стоят денег:** качественные VPN требуют подписки, а бесплатные крадут и продают трафик.
* ❌ **Неудобно для разработчиков:** IDE (Cursor, VS Code) и Python-скрипты постоянно спотыкаются об ошибки `HTTP 451 Unavailable For Legal Reasons` или `HTTP 403 Country, region, or territory not supported`.

---

## 🎯 Решение: 451bypass

**451bypass** работает по принципу **умного целевого шлюза (Smart DNS / Proxy Gateway)**:
1. Весь ваш обычный трафик (YouTube, игры, Steam, Telegram, банки, браузер) идёт **напрямую на максимальной скорости вашего провайдера**.
2. Запросы к заблокированным AI-сервисам (NVIDIA NIM, OpenAI, Anthropic, xAI Grok, Perplexity и ещё **470+ доменам**) направляются через ваш **персональный Cloudflare Worker**, который подменяет гео-заголовки и возвращает чистый ответ за миллисекунды.
3. **100% бесплатно:** работает на вашем личном бесплатном тарифе Cloudflare (до 100 000 запросов в сутки).

---

## ⚡ Установка в 1 клик (PowerShell)

Откройте PowerShell (от имени пользователя или Администратора) и вставьте:

```powershell
irm https://raw.githubusercontent.com/nebylotech/451bypass/main/install.ps1 | iex
```

*(или скачайте репозиторий и дважды кликните `setup.bat`)*.

### Что сделает установщик:
* Проверит окружение Windows и Python 3.
* Автоматически развернёт персональный Cloudflare Worker.
* Подтянет актуальную базу из 470+ сервисов.
* Зарегистрирует тихую авто-службу синхронизации в Планировщике Windows.
* Добавит глобальную команду `451b` в ваш терминал.

---

## 🖥 Интерактивная консоль (`451b`)

Просто наберите в любом терминале (PowerShell, CMD, терминал VS Code или Cursor):

```cmd
451b
```

Откроется полноэкранное меню:

```text
===============================================================
     451bypass v1.0.0 -- AI Gateway & Regional Restriction Bypass
===============================================================
  Active Domains: 477 (477 core, 0 custom)
  Gateway URL:    https://ai-gateway.whyx1ere.workers.dev
---------------------------------------------------------------
  [1] Check Service     - Проверка шлюза, воркера и Windows-службы
  [2] Test Domains      - Проверка обхода блокировок 451/403 в реальном времени
  [3] Update Domains    - Проверка и синхронизация свежих списков с GitHub
  [4] Custom Domains    - Редактировать свои домены в Блокноте (авто-дедупликация)
  [5] Run Diagnostics   - Полная 8-точечная диагностика шлюза
  [0] Exit
===============================================================
```

---

## 🛠 Быстрые команды CLI

| Команда | Описание |
|---|---|
| `451b` | Запустить главное интерактивное меню |
| `451b test <domain>` | Проверить обход блокировки для домена (например: `451b test integrate.api.nvidia.com`) |
| `451b status` | Мгновенный статус подключения шлюза и фоновой службы |
| `451b domains list` | Список всех активных маршрутизируемых доменов |
| `451b domains add <domain>` | Добавить свой сервис в `custom.txt` и выгрузить на воркер |
| `451b domains remove <domain>` | Удалить личный домен |
| `451b import` | Открыть `custom.txt` в Notepad для массового добавления |
| `451b sync` | Принудительно синхронизировать правила с Cloudflare |
| `451b diagnostics` | Комплексная диагностика (DNS, TLS, Ping, API, Worker) |
| `451b service status` | Проверить состояние службы автосинхронизации Windows |

---

## 💻 Использование в Python, Cursor и LangChain

Шлюз поддерживает **универсальный мультидоменный роутинг** (`https://<ваш-воркер>/<домен>/v1/...`).

### 1. OpenAI SDK (Python)

```python
from openai import OpenAI

# Работаем с OpenAI без VPN:
client_openai = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.openai.com/v1",
    api_key="sk-..."
)

# Работаем с NVIDIA NIM (100% обход HTTP 451):
client_nvidia = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/integrate.api.nvidia.com/v1",
    api_key="nvapi-..."
)

# Работаем с xAI Grok (обход HTTP 403):
client_grok = OpenAI(
    base_url="https://ai-gateway.whyx1ere.workers.dev/api.x.ai/v1",
    api_key="xai-..."
)

response = client_nvidia.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    messages=[{"role": "user", "content": "Привет! Как работает обход?"}]
)
print(response.choices[0].message.content)
```

### 2. Cursor / VS Code Continue

В настройках Custom OpenAI Base URL укажите:
```text
https://ai-gateway.whyx1ere.workers.dev/api.openai.com/v1
```

---

## 🧩 Умный файл `custom.txt`

Хотите добавить корпоративный сервис или новый AI?
1. Введите `451b import` — откроется Блокнот.
2. Вставьте ваши домены (по одному на строку).
3. Сохраните и закройте файл.

**Магия дедупликации:** `451bypass` сам сверит ваш `custom.txt` с базовыми правилами на воркере. Если вы случайно добавите домен, который уже есть в базе — программа **сама удалит дубликаты**, сохранив файл чистым и бесконфликтным, а уникальные сервисы мгновенно зальёт в воркер!

---

## 🌐 Какие сервисы поддерживаются из коробки (470+ доменов)?

* 🟢 **NVIDIA NIM & Developer:** `integrate.api.nvidia.com`, `build.nvidia.com`, `api.ngc.nvidia.com` (100% фикс ошибки 451).
* 🟢 **OpenAI / ChatGPT / Sora:** `api.openai.com`, `chatgpt.com`, `oaistatic.com`, `sora.com`.
* 🟢 **Anthropic Claude:** `api.anthropic.com`, `claude.ai`.
* 🟢 **xAI Grok:** `api.x.ai`, `grok.com`.
* 🟢 **AI Провайдеры:** Groq, DeepSeek, Mistral, Perplexity, ElevenLabs, Cohere, OpenRouter.
* 🟢 **Dev Tools:** Cursor, Notion, JetBrains AI, Canva, Netlify, Docker, GitHub Copilot.

---

## 🛡 Архитектура и приватность

* 🔒 **Ваши API-ключи в безопасности:** Cloudflare Worker запускается на **вашем личном** аккаунте Cloudflare. Никакие третьи лица не имеют доступа к вашим запросам или ключам.
* ⚡ **Zero-Buffering Streaming (SSE):** потоковая генерация токенов передаётся в реальном времени без задержек.
* 🌍 **Geo-Spoofing:** заголовки `Host`, `x-forwarded-for` и `x-real-ip` прозрачно заменяются на зарубежные IP Cloudflare Edge.
* 🔄 **Авто-обновление списков:** база доменов динамически кэшируется воркером с GitHub Raw — вы всегда получаете свежие правила без пересборки утилит.

---

<p align="center">
  Создано с ❤️ для свободного доступа к современным AI-технологиям.<br>
  <b>Star ⭐ репозиторий, если проект оказался полезен!</b>
</p>
