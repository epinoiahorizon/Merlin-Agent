<div dir="rtl">

<p align="center">
  <img src="assets/banner.png" alt="Merlin Agent" width="100%">
</p>

# ہرمیس ایجنٹ ☤ (Merlin Agent)

<p align="center">
  <a href="https://docs.withmerlin.online/docs/"><img src="https://img.shields.io/badge/Docs-merlin--agent.epinoiahorizon.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/merlin-agent"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/epinoiahorizon/Merlin-Agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://epinoiahorizon.com"><img src="https://img.shields.io/badge/Built%20by-Epinoia%20Horizon-blueviolet?style=for-the-badge" alt="Built by Epinoia Horizon"></a>
  <a href="README.md"><img src="https://img.shields.io/badge/Lang-English-lightgrey?style=for-the-badge" alt="English"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
</p>

> **اصل و نسب، سب سے پہلے۔** Merlin Agent، [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT، © 2025 Nous Research) کی نئی برانڈنگ کے ساتھ تقسیم ہے۔ ایجنٹ کور، ٹولز، گیٹ وے، اسکلز انجن، شیڈولر، ڈیسک ٹاپ شیل اور TUI اپ اسٹریم کوڈ ہیں — یہ ہم نے نہیں لکھے اور نہ ان پر دعویٰ کرتے ہیں۔ تبدیلیوں کی فہرست [NOTICE](NOTICE) میں اور لائسنس [LICENSE](LICENSE) میں ہے۔ Nous Research اس فورک کی توثیق نہیں کرتا۔ اصل پروجیکٹ کے لیے وہاں جائیں: وہ ہم سے آگے ہے۔
>
> اس ریپوزٹری کی git ہسٹری 2026-09-30 کو فورک امپورٹ سے شروع ہوتی ہے؛ اپ اسٹریم کی ہسٹری یہاں شامل نہیں۔

**Merlin Agent اس اوپن سورس ایجنٹ کی ڈیسک ٹاپ پیکج شدہ تقسیم ہے، جسے [Epinoia Horizon](https://epinoiahorizon.com) بناتا اور سپورٹ کرتا ہے۔** تجربے سے مہارتیں بنانا، استعمال میں بہتر کرنا اور پرانی گفتگو تلاش کرنا — یہ سب اپ اسٹریم کور ہے، جس کا ذکر اوپر ہے۔ Merlin اس کے گرد تقسیم ہے: بغیر ٹرمینل کے انسٹالر اور ایپ ونڈو، پانچ API کیز جمع نہ کرنے والوں کے لیے [Atlas Portal](https://portal.epinoiahorizon.com)، ہماری Windows سپورٹ، اور ہماری اپنی اصلاحات۔

آپ اپنی مرضی کا کوئی بھی ماڈل استعمال کر سکتے ہیں — [Atlas Portal](https://portal.epinoiahorizon.com)، [OpenRouter](https://openrouter.ai) (200 سے زائد ماڈلز)، [NovitaAI](https://novita.ai) (ماڈل API، ایجنٹ سینڈ باکس، اور GPU کلاؤڈ کے لیے اے آئی مقامی کلاؤڈ)، [NVIDIA NIM](https://build.nvidia.com) (Nemotron)، [Xiaomi MiMo](https://platform.xiaomimimo.com)، [z.ai/GLM](https://z.ai)، [Kimi/Moonshot](https://platform.moonshot.ai)، [MiniMax](https://www.minimax.io)، [Hugging Face](https://huggingface.co)، OpenAI، یا اپنا حسب ضرورت اینڈ پوائنٹ (endpoint) استعمال کریں۔ ماڈل تبدیل کرنے کے لیے صرف `merlin model` استعمال کریں — کسی کوڈ کو تبدیل کرنے کی ضرورت نہیں، کوئی پابندی نہیں۔

<table>
<tr><td><b>حقیقی ٹرمینل انٹرفیس</b></td><td>مکمل TUI جس میں ملٹی لائن ایڈیٹنگ، سلیش-کمانڈ آٹو کمپلیٹ، بات چیت کی ہسٹری، انٹرپٹ اور ری ڈائریکٹ، اور سٹریمنگ ٹول آؤٹ پٹ شامل ہے۔</td></tr>
<tr><td><b>یہ وہاں موجود ہے جہاں آپ ہیں</b></td><td>ٹیلی گرام، ڈسکارڈ (Discord)، سلیک (Slack)، واٹس ایپ (WhatsApp)، سگنل (Signal)، اور CLI — سب ایک ہی گیٹ وے پروسیس سے کام کرتے ہیں۔ وائس میمو (Voice memo) ٹرانسکرپشن، کراس پلیٹ فارم بات چیت کا تسلسل۔</td></tr>
<tr><td><b>سیکھنے کا ایک مکمل عمل</b></td><td>ایجنٹ کی اپنی ترتیب دی گئی میموری، جس میں وہ خود کو وقتاً فوقتاً یاد دہانی کرواتا ہے۔ پیچیدہ کاموں کے بعد خود کار طریقے سے مہارت (skill) کی تخلیق۔ استعمال کے دوران مہارتوں میں بہتری۔ LLM سمرائزیشن کے ساتھ FTS5 سیشن سرچ تاکہ پرانے سیشنز کی یاددہانی کی جا سکے۔ <a href="https://github.com/plastic-labs/honcho">Honcho</a> کے ذریعے صارف کی ماڈلنگ۔ <a href="https://agentskills.io">agentskills.io</a> اوپن سٹینڈرڈ کے ساتھ مکمل مطابقت۔</td></tr>
<tr><td><b>شیڈول کی گئی خودکار کارروائیاں</b></td><td>بلٹ ان (Built-in) کرون (cron) شیڈیولر جو کسی بھی پلیٹ فارم پر ڈیلیوری کے لیے استعمال ہو سکتا ہے۔ روزانہ کی رپورٹس، رات کے بیک اپس، ہفتہ وار آڈٹس — یہ سب کچھ قدرتی زبان (natural language) میں اور بغیر کسی نگرانی کے کام کرتا ہے۔</td></tr>
<tr><td><b>کام کی تقسیم اور متوازی عمل</b></td><td>متوازی (parallel) کاموں کے لیے الگ سے ذیلی ایجنٹس (subagents) بنائیں۔ پائتھون (Python) سکرپٹس لکھیں جو RPC کے ذریعے ٹولز کو استعمال کریں، تاکہ کئی مراحل پر مشتمل کاموں کو بغیر کسی سیاق و سباق (context) کے خرچ کے، ایک ہی باری میں انجام دیا جا سکے۔</td></tr>
<tr><td><b>کہیں بھی چلائیں، صرف اپنے لیپ ٹاپ پر نہیں</b></td><td>چھ (Six) ٹرمینل بیک اینڈز — لوکل، Docker، SSH، Singularity، Modal، اور Daytona۔ ڈیٹونا (Daytona) اور موڈل (Modal) سرور لیس (serverless) فعالیت پیش کرتے ہیں — جب آپ کا ایجنٹ فارغ ہوتا ہے تو اس کا ماحول سلیپ (hibernate) ہو جاتا ہے اور ضرورت پڑنے پر خود بخود جاگ جاتا ہے، جس کی وجہ سے سیشنز کے درمیان لاگت تقریباً صفر رہتی ہے۔ اسے $5 والے VPS یا GPU کلسٹر پر چلائیں۔</td></tr>
<tr><td><b>تحقیق کے لیے تیار</b></td><td>بیچ (Batch) ٹریجیکٹری (trajectory) جنریشن، اگلی نسل کے ٹول کالنگ ماڈلز کی تربیت کے لیے ٹریجیکٹری کمپریشن۔</td></tr>
</table>

---

## فوری انسٹالیشن (Quick Install)

### لینکس (Linux)، میک او ایس (macOS)، ڈبلیو ایس ایل ٹو (WSL2)

<div dir="ltr">

```bash
curl -fsSL https://withmerlin.online/install.sh | bash
```

</div>

### ونڈوز (نیٹو، پاور شیل)

> **توجہ فرمائیں:** مقامی ونڈوز (Native Windows) پر ہرمیس بغیر WSL کے چلتا ہے — CLI، گیٹ وے، TUI، اور ٹولز سب مقامی طور پر کام کرتے ہیں۔ اگر آپ WSL2 استعمال کرنا پسند کرتے ہیں، تو اوپر دی گئی لینکس/میک او ایس کی کمانڈ وہاں بھی کام کرے گی۔ کوئی مسئلہ نظر آیا؟ براہ کرم [مسائل (issues) درج کریں](https://github.com/epinoiahorizon/Merlin-Agent/issues)۔

اسے پاور شیل (PowerShell) میں چلائیں:

<div dir="ltr">

```powershell
iex (irm https://withmerlin.online/install.ps1)
```

</div>

سورس انسٹالر Python 3.14، Node.js، npm، ripgrep، FFmpeg اور Python کی
ڈیپینڈینسیز کے لیے PM استعمال کرتا ہے۔ اگر Git موجود نہ ہو تو Git for Windows
کا تصدیق شدہ آرکائیو ہرمیس کے ٹول اسٹور میں نصب کرتا ہے۔ سسٹم کا Git تبدیل نہیں
ہوتا۔ MSIX/App Installer ایک الگ پیکیج ہے۔

> **اینڈرائیڈ / ٹرمکس (Android / Termux):** aarch64 آلات کے لیے آزمائشی APT پیکیج دستیاب ہے۔ اس میں Python، Node.js اور TUI شامل ہیں۔ ڈیسک ٹاپ اور سرور کے انسٹالیشن اسکرپٹ کے بجائے [Termux گائیڈ](https://docs.withmerlin.online/docs/getting-started/termux) استعمال کریں۔
>
> **ونڈوز (Windows):** مقامی سورس انسٹال کے لیے اوپر دیا گیا PowerShell کمانڈ استعمال کریں۔ WSL2 میں لینکس کمانڈ استعمال ہوتا ہے۔ مقامی ڈیٹا `%LOCALAPPDATA%\merlin` میں اور WSL2 کا ڈیٹا `~/.merlin` میں ہوتا ہے۔ ڈیش بورڈ چیٹ مقامی Windows پر pywinpty/ConPTY استعمال کرتا ہے؛ پلیٹ فارم کی حدود [Windows گائیڈ](https://docs.withmerlin.online/docs/user-guide/windows-native) میں درج ہیں۔

انسٹالیشن کے بعد:

<div dir="ltr">

```bash
source ~/.bashrc    # شیل کو ری لوڈ کریں (یا: source ~/.zshrc)
merlin              # بات چیت شروع کریں!
```

</div>

---

## آغاز کریں (Getting Started)

<div dir="ltr">

```bash
merlin              # انٹرایکٹو CLI — بات چیت شروع کریں
merlin model        # اپنا LLM پرووائیڈر اور ماڈل منتخب کریں
merlin tools        # کنفیگر کریں کہ کون سے ٹولز ایکٹو ہیں
merlin config set   # انفرادی کنفگ (config) ویلیوز سیٹ کریں
merlin gateway      # میسجنگ گیٹ وے شروع کریں (ٹیلی گرام، ڈسکارڈ، وغیرہ)
merlin setup        # مکمل سیٹ اپ وزرڈ چلائیں (یہ سب کچھ ایک ساتھ کنفیگر کر دے گا)
merlin claw migrate # OpenClaw سے مائیگریٹ کریں (اگر آپ OpenClaw سے آ رہے ہیں)
merlin update       # لیٹسٹ ورژن پر اپ ڈیٹ کریں
merlin doctor       # کسی بھی مسئلے کی تشخیص کریں
```

</div>

📖 **[مکمل دستاویزات →](https://docs.withmerlin.online/docs/)**

---

## API-کیز اکٹھی کرنے سے بچیں — Atlas Portal

ہرمیس آپ کے پسندیدہ پرووائیڈر کے ساتھ کام کرتا ہے — یہ چیز تبدیل نہیں ہو رہی۔ لیکن اگر آپ ماڈل، ویب سرچ، امیج جنریشن، TTS، اور کلاؤڈ براؤزر کے لیے پانچ الگ الگ API کیز جمع نہیں کرنا چاہتے، تو **[Atlas Portal](https://portal.epinoiahorizon.com)** ان سب کو ایک ہی سبسکرپشن کے تحت کور کرتا ہے:

- **300+ ماڈلز** — ان میں سے کوئی بھی ماڈل `/model <name>` کے ذریعے منتخب کریں
- **ٹول گیٹ وے (Tool Gateway)** — ویب سرچ، امیج جنریشن (FAL)، ٹیکسٹ ٹو سپیچ (OpenAI)، کلاؤڈ براؤزر (Browser Use)، یہ سب آپ کی سبسکرپشن کے ذریعے چلتے ہیں۔ کسی اضافی اکاؤنٹ کی ضرورت نہیں۔

نئی انسٹالیشن کے بعد بس ایک کمانڈ کی ضرورت ہے:

<div dir="ltr">

```bash
merlin setup --portal
```

</div>

یہ آپ کو OAuth کے ذریعے لاگ ان کرواتا ہے، Atlas کو آپ کا پرووائیڈر مقرر کرتا ہے، اور ٹول گیٹ وے کو آن کر دیتا ہے۔ `merlin portal info` کمانڈ استعمال کر کے آپ کسی بھی وقت چیک کر سکتے ہیں کہ کون کون سی سروسز منسلک ہیں۔ مکمل تفصیلات [Tool Gateway دستاویزات کے صفحے](https://docs.withmerlin.online/docs/user-guide/features/tool-gateway) پر موجود ہیں۔

آپ اب بھی کسی بھی ٹول کے لیے اپنی مرضی کی API کیز استعمال کر سکتے ہیں — گیٹ وے ہر سروس کے لیے الگ الگ کام کرتا ہے، ایسا نہیں کہ یا تو سب کچھ استعمال کریں یا کچھ بھی نہیں۔

---

## CLI بمقابلہ میسجنگ فوری حوالہ

ہرمیس کے دو بنیادی انٹر فیس ہیں: آپ ٹرمینل UI کو `merlin` کے ساتھ شروع کریں، یا گیٹ وے چلا کر اس کے ساتھ ٹیلی گرام، ڈسکارڈ، سلیک، واٹس ایپ، سگنل، یا ای میل کے ذریعے بات کریں۔ جب آپ کسی بات چیت میں ہوتے ہیں، تو بہت سی سلیش (slash) کمانڈز دونوں انٹرفیسز میں ایک جیسی ہوتی ہیں۔

<div dir="ltr">

| کارروائی (Action)                         | سی ایل آئی (CLI)                              | میسجنگ پلیٹ فارمز (Messaging platforms)                                          |
| --------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------------------- |
| بات چیت شروع کریں                       | `merlin`                                      | `merlin gateway setup` اور `merlin gateway start` چلائیں، پھر بوٹ کو میسج بھیجیں |
| نئی بات چیت شروع کریں                   | `/new` یا `/reset`                            | `/new` یا `/reset`                                                               |
| ماڈل تبدیل کریں                         | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| پرسنلٹی (Personality) سیٹ کریں           | `/personality [name]`                         | `/personality [name]`                                                            |
| پچھلی باری کو دوبارہ یا منسوخ (undo) کریں | `/retry`، `/undo`                             | `/retry`، `/undo`                                                                |
| کانٹیکسٹ (context) کمپریس کریں / استعمال چیک کریں | `/compress`، `/usage`، `/insights [--days N]` | `/compress`، `/usage`، `/insights [days]`                                        |
| مہارتیں (Skills) براؤز کریں             | `/skills` یا `/<skill-name>`                  | `/<skill-name>`                                                                  |
| موجودہ کام کو روکیں                     | `Ctrl+C` دبائیں یا نیا میسج بھیجیں            | `/stop` یا نیا میسج بھیجیں                                                       |
| پلیٹ فارم کے لحاظ سے سٹیٹس              | `/platforms`                                  | `/status`، `/sethome`                                                            |

</div>

مکمل کمانڈ لسٹ کے لیے، [CLI گائیڈ](https://docs.withmerlin.online/docs/user-guide/cli) اور [میسجنگ گیٹ وے گائیڈ](https://docs.withmerlin.online/docs/user-guide/messaging) دیکھیں۔

---

## دستاویزات (Documentation)

تمام دستاویزات **[docs.withmerlin.online/docs](https://docs.withmerlin.online/docs/)** پر موجود ہیں:

<div dir="ltr">

| سیکشن (Section)                                                                                     | تفصیل (What's Covered)                                     |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [فوری آغاز (Quickstart)](https://docs.withmerlin.online/docs/getting-started/quickstart)     | انسٹالیشن → سیٹ اپ → 2 منٹ میں پہلی بات چیت شروع کریں       |
| [CLI کا استعمال](https://docs.withmerlin.online/docs/user-guide/cli)                         | کمانڈز، کی بائنڈنگز (keybindings)، پرسنلٹیز (personalities)، سیشنز |
| [کنفیگریشن (Configuration)](https://docs.withmerlin.online/docs/user-guide/configuration)    | کنفگ فائل، پرووائیڈرز، ماڈلز، اور تمام آپشنز               |
| [میسجنگ گیٹ وے](https://docs.withmerlin.online/docs/user-guide/messaging)                    | ٹیلی گرام، ڈسکارڈ، سلیک، واٹس ایپ، سگنل، ہوم اسسٹنٹ         |
| [سیکیورٹی (Security)](https://docs.withmerlin.online/docs/user-guide/security)              | کمانڈ کی منظوری، DM پیئرنگ (pairing)، کنٹینر آئسولیشن       |
| [ٹولز اور ٹول سیٹس](https://docs.withmerlin.online/docs/user-guide/features/tools)          | 40 سے زائد ٹولز، ٹول سیٹ سسٹم، ٹرمینل بیک اینڈز             |
| [مہارتوں کا سسٹم (Skills System)](https://docs.withmerlin.online/docs/user-guide/features/skills)| پروسیجرل (Procedural) میموری، سکلز ہب، نئی مہارتیں بنانا    |
| [میموری (Memory)](https://docs.withmerlin.online/docs/user-guide/features/memory)            | مستقل میموری، یوزر پروفائلز، بہترین طریقہ کار              |
| [MCP انضمام (Integration)](https://docs.withmerlin.online/docs/user-guide/features/mcp)      | صلاحیتوں کو بڑھانے کے لیے کسی بھی MCP سرور کو جوڑیں        |
| [کرون (Cron) شیڈیولنگ](https://docs.withmerlin.online/docs/user-guide/features/cron)         | پلیٹ فارم ڈیلیوری کے ساتھ شیڈول کیے گئے کام                 |
| [کانٹیکسٹ (Context) فائلز](https://docs.withmerlin.online/docs/user-guide/features/context-files)| پروجیکٹ کا سیاق و سباق (context) جو ہر بات چیت پر اثر انداز ہوتا ہے |
| [آرکیٹیکچر (Architecture)](https://docs.withmerlin.online/docs/developer-guide/architecture) | پروجیکٹ کا ڈھانچہ، ایجنٹ لوپ، اہم کلاسز                    |
| [تعاون (Contributing)](https://docs.withmerlin.online/docs/developer-guide/contributing)     | ڈیویلپمنٹ سیٹ اپ، PR کا طریقہ کار، کوڈنگ کا انداز          |
| [CLI حوالہ جات (Reference)](https://docs.withmerlin.online/docs/reference/cli-commands)      | تمام کمانڈز اور فلیگز (flags)                              |
| [انوائرمنٹ ویری ایبلز](https://docs.withmerlin.online/docs/reference/environment-variables)  | مکمل انوائرمنٹ ویری ایبل حوالہ جات                         |

</div>

---

## OpenClaw سے منتقلی

اگر آپ OpenClaw سے منتقل ہو رہے ہیں، تو ہرمیس آپ کی سیٹنگز، یادیں (memories)، مہارتیں (skills)، اور API کیز کو خود بخود امپورٹ کر سکتا ہے۔

**پہلی بار سیٹ اپ کے دوران:** سیٹ اپ وزرڈ (`merlin setup`) خود بخود `~/.openclaw` کو پہچان لیتا ہے اور کنفیگریشن شروع ہونے سے پہلے مائیگریٹ (migrate) کرنے کا آپشن دیتا ہے۔

**انسٹالیشن کے بعد کسی بھی وقت:**

<div dir="ltr">

```bash
merlin claw migrate              # انٹرایکٹو مائیگریشن (مکمل پری سیٹ)
merlin claw migrate --dry-run    # جائزہ لیں کہ کیا کیا مائیگریٹ ہوگا
merlin claw migrate --preset user-data   # حساس معلومات (secrets) کے بغیر مائیگریٹ کریں
merlin claw migrate --overwrite  # موجودہ متصادم فائلوں کو اوور رائٹ کریں
```

</div>

جو چیزیں امپورٹ ہوتی ہیں:

- **SOUL.md** — پرسونا (persona) فائل
- **میموریز (Memories)** — MEMORY.md اور USER.md کی اندراجات
- **مہارتیں (Skills)** — صارف کی بنائی گئی مہارتیں → `~/.merlin/skills/openclaw-imports/`
- **کمانڈ الاؤ لسٹ (allowlist)** — منظوری کے پیٹرنز (approval patterns)
- **میسجنگ سیٹنگز** — پلیٹ فارم کنفیگریشنز، اجازت یافتہ صارفین، ورکنگ ڈائریکٹری
- **API کیز** — الاؤ لسٹ شدہ حساس معلومات (ٹیلی گرام، OpenRouter، OpenAI، Anthropic، ElevenLabs)
- **TTS اثاثے** — ورک اسپیس کی آڈیو فائلیں
- **ورک اسپیس کی ہدایات** — AGENTS.md (`--workspace-target` کے ساتھ)

تمام آپشنز دیکھنے کے لیے `merlin claw migrate --help` استعمال کریں، یا انٹرایکٹو ایجنٹ کی مدد سے مائیگریٹ کرنے کے لیے `openclaw-migration` سکل کا استعمال کریں (جس میں ڈرائی رن (dry-run) پریویوز شامل ہیں)۔

---

## تعاون کریں (Contributing)

ہم آپ کے تعاون کا خیرمقدم کرتے ہیں! ڈیویلپمنٹ سیٹ اپ، کوڈ کے انداز اور PR کے طریقہ کار کے لیے براہ کرم ہماری [Contributing گائیڈ](https://docs.withmerlin.online/docs/developer-guide/contributing) دیکھیں۔

PM اور Python 3.14 کے ٹیسٹ ماحول اور تصدیقی کمانڈز کے لیے
[Development Setup](CONTRIBUTING.md#development-setup) دیکھیں۔

---

## کمیونٹی (Community)

- 💬 [ڈسکارڈ (Discord)](https://discord.gg/merlin-agent)
- 📚 [سکلز ہب (Skills Hub)](https://agentskills.io)
- 🐛 [مسائل (Issues)](https://github.com/epinoiahorizon/Merlin-Agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — ہرمیس اور دیگر MCP ہوسٹس کے لیے لینکس (Linux) ڈیسک ٹاپ کنٹرول MCP سرور، جس میں AT-SPI ایکسیسیبلٹی ٹریز، Wayland/X11 ان پٹ، سکرین شاٹس، اور کمپوزیٹر ونڈو ٹارگیٹنگ شامل ہے۔
- 🔌 [MerlinClaw](https://github.com/AaronWong1999/merlinclaw) — کمیونٹی وی چیٹ (WeChat) برج: ہرمیس ایجنٹ اور OpenClaw کو ایک ہی وی چیٹ اکاؤنٹ پر چلائیں۔

---

## لائسنس (License)

MIT — تفصیلات کے لیے [LICENSE](LICENSE) دیکھیں۔

Merlin Agent، Nous Research کے [hermes-agent](https://github.com/NousResearch/hermes-agent) کا ترمیم شدہ فورک ہے، جو MIT لائسنس کے تحت استعمال ہوتا ہے۔ اصل کاپی رائٹ اطلاع [LICENSE](LICENSE) میں محفوظ ہے اور تبدیلیوں کی فہرست [NOTICE](NOTICE) میں ہے۔ Nous Research اس فورک کی توثیق نہیں کرتا۔

[نوس ریسرچ (Epinoia Horizon)](https://epinoiahorizon.com) کی جانب سے تیار کردہ۔

</div>
